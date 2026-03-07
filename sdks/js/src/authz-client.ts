import { AuthzLocalStorageStore } from './authz-storage'
import { isTokenExpired, tokenToUser } from './jwt-utils'
import { warnIfInsecure } from './warn-insecure'
import type {
  SentinelAuthzConfig,
  AuthzTokenStore,
  AuthzResolveResponse,
  IdpConfig,
} from './authz-types'
import type { SentinelUser } from './types'

type AuthStateListener = (user: SentinelUser | null) => void

/**
 * Browser auth client for Sentinel AuthZ mode.
 * Manages dual tokens: IdP token (identity) + Sentinel authz token (authorization).
 */
export class SentinelAuthz {
  private readonly sentinelUrl: string
  private readonly store: AuthzTokenStore
  private readonly autoRefresh: boolean
  private readonly refreshBuffer: number
  private readonly idps: Record<string, IdpConfig>
  private readonly redirectUri: string
  private refreshTimer: ReturnType<typeof setTimeout> | null = null
  private refreshPromise: Promise<boolean> | null = null
  private listeners: Set<AuthStateListener> = new Set()

  constructor(config: SentinelAuthzConfig) {
    this.sentinelUrl = config.sentinelUrl.replace(/\/+$/, '')
    this.store = config.storage ?? new AuthzLocalStorageStore()
    this.autoRefresh = config.autoRefresh ?? true
    this.refreshBuffer = config.refreshBuffer ?? 30
    this.idps = config.idps ?? {}
    this.redirectUri = config.redirectUri
      ?? (typeof window !== 'undefined' ? `${window.location.origin}/auth/callback` : '')
    warnIfInsecure(this.sentinelUrl, 'SentinelAuthz')

    if (this.autoRefresh && this.store.getAuthzToken()) {
      this.scheduleRefresh()
    }
  }

  // ── Login ───────────────────────────────────────────────────────────

  /** Redirect to IdP login page. Requires the provider to be configured in `idps`. */
  login(provider: string): void {
    const idp = this.idps[provider]
    if (!idp) {
      throw new Error(
        `IdP "${provider}" not configured. Pass it via idps in SentinelAuthzConfig, ` +
        `e.g. { idps: { google: IdpConfigs.google('your-client-id') } }`
      )
    }

    const nonce = crypto.randomUUID()
    sessionStorage.setItem('sentinel_authz_nonce', nonce)
    sessionStorage.setItem('sentinel_authz_provider', provider)

    const params = new URLSearchParams({
      client_id: idp.clientId,
      redirect_uri: this.redirectUri,
      response_type: idp.responseType ?? 'id_token',
      scope: (idp.scopes ?? ['openid', 'email', 'profile']).join(' '),
      nonce,
      ...idp.extraParams,
    })

    window.location.href = `${idp.authorizationUrl}?${params}`
  }

  /**
   * Handle the OAuth callback. Extracts the id_token from the URL hash,
   * calls resolve, and returns the result.
   *
   * Call this from your callback route. Returns null if no hash is present.
   */
  handleCallback(): { idpToken: string; provider: string } | null {
    const hash = window.location.hash.substring(1)
    if (!hash) return null

    const params = new URLSearchParams(hash)
    const idpToken = params.get('id_token')
    const error = params.get('error')

    if (error) {
      throw new Error(params.get('error_description') || error)
    }
    if (!idpToken) return null

    // Clean the URL
    window.history.replaceState({}, '', window.location.pathname)

    const provider = sessionStorage.getItem('sentinel_authz_provider') || 'google'
    sessionStorage.removeItem('sentinel_authz_nonce')
    sessionStorage.removeItem('sentinel_authz_provider')

    return { idpToken, provider }
  }

  // ── Auth flow ───────────────────────────────────────────────────────

  /** Resolve an IdP token to discover the user's available workspaces. */
  async resolve(idpToken: string, provider: string): Promise<AuthzResolveResponse> {
    const res = await fetch(`${this.sentinelUrl}/authz/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idp_token: idpToken, provider }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error((body as Record<string, string>).detail || `HTTP ${res.status}`)
    }
    return res.json()
  }

  /** Select a workspace and exchange the IdP token for a Sentinel authz token. */
  async selectWorkspace(idpToken: string, provider: string, workspaceId: string): Promise<void> {
    const res = await fetch(`${this.sentinelUrl}/authz/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        idp_token: idpToken,
        provider,
        workspace_id: workspaceId,
      }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error((body as Record<string, string>).detail || 'Token exchange failed')
    }

    const data: AuthzResolveResponse = await res.json()
    if (!data.authz_token) {
      throw new Error('No authz token in response')
    }

    this.store.setTokens(idpToken, data.authz_token, provider, workspaceId)
    this.notify()
    if (this.autoRefresh) this.scheduleRefresh()
  }

  // ── Token access ──────────────────────────────────────────────────

  /** Parse the current authz token into a SentinelUser, or null. */
  getUser(): SentinelUser | null {
    const token = this.store.getAuthzToken()
    if (!token) return null
    try {
      if (isTokenExpired(token)) return null
      return tokenToUser(token)
    } catch {
      return null
    }
  }

  /** True if a non-expired authz token exists. */
  get isAuthenticated(): boolean {
    const token = this.store.getAuthzToken()
    return !!token && !isTokenExpired(token)
  }

  /** Get auth headers for API requests (both IdP and authz tokens). */
  getHeaders(): Record<string, string> {
    const idpToken = this.store.getIdpToken()
    const authzToken = this.store.getAuthzToken()
    if (!idpToken || !authzToken) return {}
    return {
      Authorization: `Bearer ${idpToken}`,
      'X-Authz-Token': authzToken,
    }
  }

  // ── Fetch wrapper ─────────────────────────────────────────────────

  /** Fetch with automatic dual-token headers and 401→refresh→retry. */
  async fetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    const doFetch = () => {
      const headers = new Headers(init?.headers)
      const authHeaders = this.getHeaders()
      for (const [k, v] of Object.entries(authHeaders)) {
        headers.set(k, v)
      }
      return fetch(input, { ...init, headers })
    }

    let res = await doFetch()

    if (res.status === 401) {
      const refreshed = await this.refresh()
      if (refreshed) {
        res = await doFetch()
      }
    }

    return res
  }

  /** Fetch JSON with automatic dual-token headers, 401 retry, and response parsing. */
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

  // ── Refresh ───────────────────────────────────────────────────────

  /** Refresh the authz token using the stored IdP token. Returns true on success. */
  async refresh(): Promise<boolean> {
    if (this.refreshPromise) return this.refreshPromise
    this.refreshPromise = this._doRefresh().finally(() => {
      this.refreshPromise = null
    })
    return this.refreshPromise
  }

  private async _doRefresh(): Promise<boolean> {
    const idpToken = this.store.getIdpToken()
    const provider = this.store.getProvider()
    const workspaceId = this.store.getWorkspaceId()
    if (!idpToken || !provider || !workspaceId) return false

    try {
      await this.selectWorkspace(idpToken, provider, workspaceId)
      return true
    } catch {
      this.store.clear()
      this.clearRefreshTimer()
      this.notify()
      return false
    }
  }

  // ── Events ────────────────────────────────────────────────────────

  /** Subscribe to auth state changes. Returns an unsubscribe function. */
  onAuthStateChange(cb: AuthStateListener): () => void {
    this.listeners.add(cb)
    return () => { this.listeners.delete(cb) }
  }

  /** Clear tokens and notify listeners. */
  logout(): void {
    this.store.clear()
    this.clearRefreshTimer()
    this.notify()
  }

  /** Clean up timers. Call when done (e.g. component unmount). */
  destroy(): void {
    this.clearRefreshTimer()
    this.listeners.clear()
  }

  // ── Private ───────────────────────────────────────────────────────

  private notify(): void {
    const user = this.getUser()
    for (const cb of this.listeners) {
      try { cb(user) } catch { /* ignore listener errors */ }
    }
  }

  private scheduleRefresh(): void {
    this.clearRefreshTimer()
    const token = this.store.getAuthzToken()
    if (!token) return

    try {
      const parts = token.split('.')
      const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')))
      const expiresAt = payload.exp * 1000
      const delay = expiresAt - Date.now() - this.refreshBuffer * 1000
      if (delay <= 0) {
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
