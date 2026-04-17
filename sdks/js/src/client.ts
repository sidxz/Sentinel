import { generateCodeVerifier, deriveCodeChallenge } from './pkce'
import { MemoryStore } from './storage'
import { isTokenExpired, tokenToUser } from './jwt-utils'
import { warnIfInsecure } from './warn-insecure'
import type {
  SentinelConfig,
  SentinelUser,
  TokenResponse,
  TokenStore,
  WorkspaceOption,
} from './types'

const PKCE_KEY = 'sentinel_pkce_verifier'
const STATE_KEY = 'sentinel_oauth_state'

type AuthStateListener = (user: SentinelUser | null) => void

/**
 * Browser auth client for Sentinel. Handles PKCE, token storage, refresh, and
 * the non-standard workspace-selection auth flow.
 */
export class SentinelAuth {
  private readonly url: string
  private readonly clientId: string
  private readonly redirectUri: string
  private readonly store: TokenStore
  private readonly autoRefresh: boolean
  private readonly refreshBuffer: number
  private refreshTimer: ReturnType<typeof setTimeout> | null = null
  private refreshPromise: Promise<boolean> | null = null
  private listeners: Set<AuthStateListener> = new Set()

  constructor(config: SentinelConfig) {
    this.url = config.sentinelUrl.replace(/\/+$/, '')
    if (!config.clientId) {
      throw new Error(
        'SentinelAuth: clientId is required — obtain it from the Sentinel admin panel.',
      )
    }
    this.clientId = config.clientId
    this.redirectUri =
      config.redirectUri ??
      (typeof window !== 'undefined'
        ? `${window.location.origin}/auth/callback`
        : '')
    this.store = config.storage ?? new MemoryStore()
    this.autoRefresh = config.autoRefresh ?? true
    this.refreshBuffer = config.refreshBuffer ?? 60
    warnIfInsecure(this.url, 'SentinelAuth')

    // Schedule a refresh if we already have a valid token
    if (this.autoRefresh && this.store.getAccessToken()) {
      this.scheduleRefresh()
    }
  }

  // ── Auth flow ───────────────────────────────────────────────────────

  /** List available OAuth providers. */
  async getProviders(): Promise<string[]> {
    const res = await fetch(`${this.url}/auth/providers`)
    if (!res.ok) throw new Error('Failed to fetch providers')
    return res.json()
  }

  /** Initiate OAuth + PKCE login. Redirects the browser. */
  async login(provider: string): Promise<void> {
    const verifier = generateCodeVerifier()
    const challenge = await deriveCodeChallenge(verifier)
    sessionStorage.setItem(PKCE_KEY, verifier)

    // Generate and store a random state parameter to prevent CSRF
    const stateBytes = new Uint8Array(16)
    crypto.getRandomValues(stateBytes)
    const state = Array.from(stateBytes, (b) => b.toString(16).padStart(2, '0')).join('')
    sessionStorage.setItem(STATE_KEY, state)

    const params = new URLSearchParams({
      client_id: this.clientId,
      redirect_uri: this.redirectUri,
      code_challenge: challenge,
      code_challenge_method: 'S256',
      state,
    })
    window.location.href = `${this.url}/auth/login/${provider}?${params}`
  }

  /**
   * Verify the OAuth state parameter from the callback URL.
   * Call this before processing the auth code. Throws if state is missing or mismatched.
   */
  verifyCallbackState(): void {
    const params = new URLSearchParams(window.location.search)
    const returnedState = params.get('state')
    const expectedState = sessionStorage.getItem(STATE_KEY)

    if (!expectedState || returnedState !== expectedState) {
      sessionStorage.removeItem(STATE_KEY)
      throw new Error('OAuth state mismatch — possible CSRF attack')
    }
    sessionStorage.removeItem(STATE_KEY)
  }

  /** Fetch available workspaces for the given auth code. */
  async getWorkspaces(code: string): Promise<WorkspaceOption[]> {
    const res = await fetch(
      `${this.url}/auth/workspaces?code=${encodeURIComponent(code)}`,
    )
    if (!res.ok) throw new Error('Failed to fetch workspaces')
    return res.json()
  }

  /** Complete token exchange with workspace selection + PKCE verifier. */
  async selectWorkspace(code: string, workspaceId: string): Promise<void> {
    const codeVerifier = sessionStorage.getItem(PKCE_KEY)
    if (!codeVerifier) throw new Error('Missing PKCE code verifier')

    const res = await fetch(`${this.url}/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code,
        workspace_id: workspaceId,
        code_verifier: codeVerifier,
      }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail || 'Token exchange failed')
    }

    const data: TokenResponse = await res.json()
    this.store.setTokens(data.access_token, data.refresh_token)
    sessionStorage.removeItem(PKCE_KEY)
    this.notify()
    if (this.autoRefresh) this.scheduleRefresh()
  }

  /** Refresh the access token using the stored refresh token. Returns true on success. */
  async refresh(): Promise<boolean> {
    if (this.refreshPromise) return this.refreshPromise
    this.refreshPromise = this._doRefresh().finally(() => {
      this.refreshPromise = null
    })
    return this.refreshPromise
  }

  private async _doRefresh(): Promise<boolean> {
    const refreshToken = this.store.getRefreshToken()
    if (!refreshToken) return false

    try {
      const res = await fetch(`${this.url}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      if (!res.ok) {
        if (res.status === 401) {
          this.store.clear()
          this.clearRefreshTimer()
          this.notify()
        }
        return false
      }

      const data: TokenResponse = await res.json()
      this.store.setTokens(data.access_token, data.refresh_token)
      this.notify()
      if (this.autoRefresh) this.scheduleRefresh()
      return true
    } catch {
      return false
    }
  }

  /** Clear tokens and notify listeners. */
  logout(): void {
    this.store.clear()
    this.clearRefreshTimer()
    this.notify()
  }

  // ── Token access ──────────────────────────────────────────────────

  /** Get the current access token (may be expired). */
  getToken(): string | null {
    return this.store.getAccessToken()
  }

  /** Parse the current access token into a SentinelUser, or null. */
  getUser(): SentinelUser | null {
    const token = this.store.getAccessToken()
    if (!token) return null
    try {
      if (isTokenExpired(token)) return null
      return tokenToUser(token)
    } catch {
      return null
    }
  }

  /** True if a non-expired access token exists. */
  get isAuthenticated(): boolean {
    const token = this.store.getAccessToken()
    return !!token && !isTokenExpired(token)
  }

  // ── Fetch wrapper ─────────────────────────────────────────────────

  /** Fetch with automatic Bearer header and 401→refresh→retry. */
  async fetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    const doFetch = (token: string | null) => {
      const headers = new Headers(init?.headers)
      if (token) headers.set('Authorization', `Bearer ${token}`)
      return fetch(input, { ...init, headers })
    }

    let res = await doFetch(this.store.getAccessToken())

    if (res.status === 401) {
      const refreshed = await this.refresh()
      if (refreshed) {
        res = await doFetch(this.store.getAccessToken())
      }
    }

    return res
  }

  /** Fetch JSON with automatic Bearer header, 401 retry, and response parsing. */
  async fetchJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
    const headers = new Headers(init?.headers)
    if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
    const res = await this.fetch(input, { ...init, headers })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error((body as Record<string, string>).detail || `HTTP ${res.status}`)
    }
    return res.json()
  }

  // ── Events ────────────────────────────────────────────────────────

  /** Subscribe to auth state changes. Returns an unsubscribe function. */
  onAuthStateChange(cb: AuthStateListener): () => void {
    this.listeners.add(cb)
    return () => {
      this.listeners.delete(cb)
    }
  }

  // ── Cleanup ───────────────────────────────────────────────────────

  /** Clean up timers. Call when done (e.g. component unmount). */
  destroy(): void {
    this.clearRefreshTimer()
    this.listeners.clear()
  }

  // ── Private ───────────────────────────────────────────────────────

  private notify(): void {
    const user = this.getUser()
    for (const cb of this.listeners) {
      try {
        cb(user)
      } catch {
        // ignore listener errors
      }
    }
  }

  private scheduleRefresh(): void {
    this.clearRefreshTimer()
    const token = this.store.getAccessToken()
    if (!token) return

    try {
      const parts = token.split('.')
      const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')))
      const expiresAt = payload.exp * 1000
      const delay = expiresAt - Date.now() - this.refreshBuffer * 1000
      if (delay <= 0) {
        // Token already near expiry, refresh immediately
        void this.refresh()
        return
      }
      this.refreshTimer = setTimeout(() => void this.refresh(), delay)
    } catch {
      // Can't parse token, skip scheduling
    }
  }

  private clearRefreshTimer(): void {
    if (this.refreshTimer !== null) {
      clearTimeout(this.refreshTimer)
      this.refreshTimer = null
    }
  }
}
