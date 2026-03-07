# JS SDK AuthZ Mode Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add authz mode support to `@sentinel-auth/js`, `@sentinel-auth/react`, and `@sentinel-auth/nextjs` so client apps can use the dual-token architecture (IdP token + Sentinel authz token) with the same developer experience as proxy mode.

**Architecture:** Browser authenticates with IdP (e.g. Google), sends IdP token to client backend's `/auth/resolve` (thin proxy to Sentinel), gets back an authz JWT. Both tokens are sent on every API call. The JS SDK manages both tokens, auto-refreshes the authz token, and provides React context/hooks parallel to the existing proxy-mode components.

**Tech Stack:** TypeScript, vitest (happy-dom), tsup, jose (already a dependency)

**Design Doc:** `docs/plans/2026-03-07-js-sdk-authz-design.md`

---

## Task 1: Authz Types (`@sentinel-auth/js`)

**Files:**
- Create: `sdks/js/src/authz-types.ts`

**Step 1: Create authz type definitions**

```ts
// sdks/js/src/authz-types.ts
import type { SentinelUser, WorkspaceRole } from './types'

export interface SentinelAuthzConfig {
  /** Base URL of the client backend (e.g. "http://localhost:9200").
   *  Derives /auth/resolve for token exchange. */
  backendUrl: string
  /** Token storage backend. Defaults to AuthzLocalStorageStore. */
  storage?: AuthzTokenStore
  /** Automatically refresh authz token before expiry. Defaults to true. */
  autoRefresh?: boolean
  /** Seconds before authz token expiry to trigger refresh. Defaults to 30. */
  refreshBuffer?: number
}

export interface AuthzTokenStore {
  getIdpToken(): string | null
  getAuthzToken(): string | null
  getProvider(): string | null
  getWorkspaceId(): string | null
  setTokens(idpToken: string, authzToken: string, provider: string, workspaceId: string): void
  clear(): void
}

export interface AuthzResolveResponse {
  user: AuthzUserInfo
  workspaces?: AuthzWorkspaceOption[]
  workspace?: AuthzWorkspaceInfo
  authz_token?: string
  expires_in?: number
}

export interface AuthzUserInfo {
  id: string
  email: string
  name: string
}

export interface AuthzWorkspaceOption {
  id: string
  name: string
  slug: string
  role: WorkspaceRole
}

export interface AuthzWorkspaceInfo {
  id: string
  slug: string
  role: WorkspaceRole
}

export { SentinelUser, WorkspaceRole }
```

**Step 2: Commit**

```bash
git add sdks/js/src/authz-types.ts
git commit -m "feat(js-sdk): add authz mode type definitions"
```

---

## Task 2: Authz Storage (`@sentinel-auth/js`)

**Files:**
- Create: `sdks/js/src/authz-storage.ts`
- Create: `sdks/js/src/__tests__/authz-storage.test.ts`

**Step 1: Write the failing test**

```ts
// sdks/js/src/__tests__/authz-storage.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { AuthzLocalStorageStore, AuthzMemoryStore } from '../authz-storage'

describe('AuthzMemoryStore', () => {
  let store: AuthzMemoryStore

  beforeEach(() => {
    store = new AuthzMemoryStore()
  })

  it('starts empty', () => {
    expect(store.getIdpToken()).toBeNull()
    expect(store.getAuthzToken()).toBeNull()
    expect(store.getProvider()).toBeNull()
    expect(store.getWorkspaceId()).toBeNull()
  })

  it('stores and retrieves all tokens', () => {
    store.setTokens('idp-jwt', 'authz-jwt', 'google', 'ws-1')
    expect(store.getIdpToken()).toBe('idp-jwt')
    expect(store.getAuthzToken()).toBe('authz-jwt')
    expect(store.getProvider()).toBe('google')
    expect(store.getWorkspaceId()).toBe('ws-1')
  })

  it('clear removes all tokens', () => {
    store.setTokens('idp-jwt', 'authz-jwt', 'google', 'ws-1')
    store.clear()
    expect(store.getIdpToken()).toBeNull()
    expect(store.getAuthzToken()).toBeNull()
    expect(store.getProvider()).toBeNull()
    expect(store.getWorkspaceId()).toBeNull()
  })
})

describe('AuthzLocalStorageStore', () => {
  let store: AuthzLocalStorageStore

  beforeEach(() => {
    localStorage.clear()
    store = new AuthzLocalStorageStore()
  })

  it('stores and retrieves from localStorage', () => {
    store.setTokens('idp-jwt', 'authz-jwt', 'google', 'ws-1')
    expect(store.getIdpToken()).toBe('idp-jwt')
    expect(store.getAuthzToken()).toBe('authz-jwt')
    expect(store.getProvider()).toBe('google')
    expect(store.getWorkspaceId()).toBe('ws-1')
    expect(localStorage.getItem('sentinel_idp_token')).toBe('idp-jwt')
  })

  it('clear removes from localStorage', () => {
    store.setTokens('idp-jwt', 'authz-jwt', 'google', 'ws-1')
    store.clear()
    expect(localStorage.getItem('sentinel_idp_token')).toBeNull()
    expect(localStorage.getItem('sentinel_authz_token')).toBeNull()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd sdks/js && npx vitest run src/__tests__/authz-storage.test.ts`
Expected: FAIL (modules not found)

**Step 3: Write the implementation**

```ts
// sdks/js/src/authz-storage.ts
import type { AuthzTokenStore } from './authz-types'

const PREFIX = 'sentinel_'

export class AuthzLocalStorageStore implements AuthzTokenStore {
  getIdpToken(): string | null {
    return localStorage.getItem(`${PREFIX}idp_token`)
  }
  getAuthzToken(): string | null {
    return localStorage.getItem(`${PREFIX}authz_token`)
  }
  getProvider(): string | null {
    return localStorage.getItem(`${PREFIX}idp_provider`)
  }
  getWorkspaceId(): string | null {
    return localStorage.getItem(`${PREFIX}workspace_id`)
  }
  setTokens(idpToken: string, authzToken: string, provider: string, workspaceId: string): void {
    localStorage.setItem(`${PREFIX}idp_token`, idpToken)
    localStorage.setItem(`${PREFIX}authz_token`, authzToken)
    localStorage.setItem(`${PREFIX}idp_provider`, provider)
    localStorage.setItem(`${PREFIX}workspace_id`, workspaceId)
  }
  clear(): void {
    localStorage.removeItem(`${PREFIX}idp_token`)
    localStorage.removeItem(`${PREFIX}authz_token`)
    localStorage.removeItem(`${PREFIX}idp_provider`)
    localStorage.removeItem(`${PREFIX}workspace_id`)
  }
}

export class AuthzMemoryStore implements AuthzTokenStore {
  private idpToken: string | null = null
  private authzToken: string | null = null
  private provider: string | null = null
  private workspaceId: string | null = null

  getIdpToken(): string | null { return this.idpToken }
  getAuthzToken(): string | null { return this.authzToken }
  getProvider(): string | null { return this.provider }
  getWorkspaceId(): string | null { return this.workspaceId }
  setTokens(idpToken: string, authzToken: string, provider: string, workspaceId: string): void {
    this.idpToken = idpToken
    this.authzToken = authzToken
    this.provider = provider
    this.workspaceId = workspaceId
  }
  clear(): void {
    this.idpToken = null
    this.authzToken = null
    this.provider = null
    this.workspaceId = null
  }
}
```

**Step 4: Run test to verify it passes**

Run: `cd sdks/js && npx vitest run src/__tests__/authz-storage.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add sdks/js/src/authz-storage.ts sdks/js/src/__tests__/authz-storage.test.ts
git commit -m "feat(js-sdk): add authz token storage implementations"
```

---

## Task 3: Authz Client (`@sentinel-auth/js`)

**Files:**
- Create: `sdks/js/src/authz-client.ts`
- Create: `sdks/js/src/__tests__/authz-client.test.ts`

**Step 1: Write the failing test**

```ts
// sdks/js/src/__tests__/authz-client.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { SentinelAuthz } from '../authz-client'
import { AuthzMemoryStore } from '../authz-storage'

// Helper to create a fake JWT with exp claim
function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: 'RS256', typ: 'JWT' }))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  const body = btoa(JSON.stringify(payload))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  return `${header}.${body}.fake-signature`
}

const authzPayload = {
  sub: 'user-1',
  email: 'alice@acme.com',
  name: 'Alice',
  wid: 'ws-1',
  wslug: 'acme',
  wrole: 'editor',
  idp_sub: 'google|123',
  groups: [],
  actions: ['notes:create'],
  aud: 'sentinel:authz',
  iss: 'sentinel',
  exp: Math.floor(Date.now() / 1000) + 300,
  iat: Math.floor(Date.now() / 1000),
  jti: 'jti-authz-1',
}

const resolveResponse = {
  user: { id: 'user-1', email: 'alice@acme.com', name: 'Alice' },
  workspaces: [
    { id: 'ws-1', name: 'Acme Corp', slug: 'acme', role: 'editor' },
  ],
}

const selectResponse = {
  user: { id: 'user-1', email: 'alice@acme.com', name: 'Alice' },
  workspace: { id: 'ws-1', slug: 'acme', role: 'editor' },
  authz_token: makeJwt(authzPayload),
  expires_in: 300,
}

describe('SentinelAuthz', () => {
  let store: AuthzMemoryStore
  let client: SentinelAuthz

  beforeEach(() => {
    store = new AuthzMemoryStore()
    client = new SentinelAuthz({
      backendUrl: 'http://localhost:9200',
      storage: store,
      autoRefresh: false,
    })
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    client.destroy()
    vi.restoreAllMocks()
  })

  it('resolve calls POST /auth/resolve with idp token and provider', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(resolveResponse), { status: 200 }),
    )

    const result = await client.resolve('idp-token-123', 'google')

    expect(fetch).toHaveBeenCalledWith('http://localhost:9200/auth/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idp_token: 'idp-token-123', provider: 'google' }),
    })
    expect(result.workspaces).toHaveLength(1)
    expect(result.workspaces![0].slug).toBe('acme')
  })

  it('selectWorkspace stores both tokens and notifies listeners', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(selectResponse), { status: 200 }),
    )

    const listener = vi.fn()
    client.onAuthStateChange(listener)

    await client.selectWorkspace('idp-token-123', 'google', 'ws-1')

    expect(fetch).toHaveBeenCalledWith('http://localhost:9200/auth/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        idp_token: 'idp-token-123',
        provider: 'google',
        workspace_id: 'ws-1',
      }),
    })

    expect(store.getIdpToken()).toBe('idp-token-123')
    expect(store.getAuthzToken()).toBe(selectResponse.authz_token)
    expect(store.getProvider()).toBe('google')
    expect(store.getWorkspaceId()).toBe('ws-1')
    expect(listener).toHaveBeenCalledTimes(1)
    expect(listener.mock.calls[0][0]).not.toBeNull()
  })

  it('getUser returns user from authz token', async () => {
    const authzToken = makeJwt(authzPayload)
    store.setTokens('idp-token', authzToken, 'google', 'ws-1')

    const user = client.getUser()
    expect(user).not.toBeNull()
    expect(user!.userId).toBe('user-1')
    expect(user!.email).toBe('alice@acme.com')
    expect(user!.workspaceRole).toBe('editor')
  })

  it('getUser returns null when no authz token', () => {
    expect(client.getUser()).toBeNull()
  })

  it('getUser returns null when authz token is expired', () => {
    const expired = makeJwt({ ...authzPayload, exp: Math.floor(Date.now() / 1000) - 60 })
    store.setTokens('idp-token', expired, 'google', 'ws-1')
    expect(client.getUser()).toBeNull()
  })

  it('getHeaders returns both Authorization and X-Authz-Token', () => {
    const authzToken = makeJwt(authzPayload)
    store.setTokens('idp-token', authzToken, 'google', 'ws-1')

    const headers = client.getHeaders()
    expect(headers).toEqual({
      Authorization: 'Bearer idp-token',
      'X-Authz-Token': authzToken,
    })
  })

  it('getHeaders returns empty object when not authenticated', () => {
    expect(client.getHeaders()).toEqual({})
  })

  it('fetch injects both headers', async () => {
    const authzToken = makeJwt(authzPayload)
    store.setTokens('idp-token', authzToken, 'google', 'ws-1')

    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    )

    await client.fetch('/api/notes')

    const calledInit = vi.mocked(fetch).mock.calls[0][1]!
    const headers = new Headers(calledInit.headers)
    expect(headers.get('Authorization')).toBe('Bearer idp-token')
    expect(headers.get('X-Authz-Token')).toBe(authzToken)
  })

  it('fetch retries on 401 after successful re-resolve', async () => {
    const authzToken = makeJwt(authzPayload)
    const newAuthzToken = makeJwt({ ...authzPayload, jti: 'jti-new' })
    store.setTokens('idp-token', authzToken, 'google', 'ws-1')

    vi.mocked(fetch)
      // First API call → 401
      .mockResolvedValueOnce(new Response('', { status: 401 }))
      // Re-resolve → new authz token
      .mockResolvedValueOnce(
        new Response(JSON.stringify({
          ...selectResponse,
          authz_token: newAuthzToken,
        }), { status: 200 }),
      )
      // Retry → success
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: 'ok' }), { status: 200 }),
      )

    const res = await client.fetch('/api/notes')
    expect(res.status).toBe(200)
    expect(fetch).toHaveBeenCalledTimes(3)
  })

  it('logout clears tokens and notifies listeners', () => {
    const authzToken = makeJwt(authzPayload)
    store.setTokens('idp-token', authzToken, 'google', 'ws-1')

    const listener = vi.fn()
    client.onAuthStateChange(listener)

    client.logout()

    expect(store.getIdpToken()).toBeNull()
    expect(store.getAuthzToken()).toBeNull()
    expect(listener).toHaveBeenCalledWith(null)
  })

  it('isAuthenticated reflects token state', () => {
    expect(client.isAuthenticated).toBe(false)
    const authzToken = makeJwt(authzPayload)
    store.setTokens('idp-token', authzToken, 'google', 'ws-1')
    expect(client.isAuthenticated).toBe(true)
  })

  it('resolve throws on HTTP error', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Invalid IdP token' }), { status: 401 }),
    )
    await expect(client.resolve('bad-token', 'google'))
      .rejects.toThrow('Invalid IdP token')
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd sdks/js && npx vitest run src/__tests__/authz-client.test.ts`
Expected: FAIL (module not found)

**Step 3: Write the implementation**

```ts
// sdks/js/src/authz-client.ts
import { AuthzLocalStorageStore } from './authz-storage'
import { isTokenExpired, tokenToUser } from './jwt-utils'
import { warnIfInsecure } from './warn-insecure'
import type {
  SentinelAuthzConfig,
  AuthzTokenStore,
  AuthzResolveResponse,
} from './authz-types'
import type { SentinelUser } from './types'

type AuthStateListener = (user: SentinelUser | null) => void

/**
 * Browser auth client for Sentinel AuthZ mode.
 * Manages dual tokens: IdP token (identity) + Sentinel authz token (authorization).
 */
export class SentinelAuthz {
  private readonly backendUrl: string
  private readonly store: AuthzTokenStore
  private readonly autoRefresh: boolean
  private readonly refreshBuffer: number
  private refreshTimer: ReturnType<typeof setTimeout> | null = null
  private refreshPromise: Promise<boolean> | null = null
  private listeners: Set<AuthStateListener> = new Set()

  constructor(config: SentinelAuthzConfig) {
    this.backendUrl = config.backendUrl.replace(/\/+$/, '')
    this.store = config.storage ?? new AuthzLocalStorageStore()
    this.autoRefresh = config.autoRefresh ?? true
    this.refreshBuffer = config.refreshBuffer ?? 30
    warnIfInsecure(this.backendUrl, 'SentinelAuthz')

    if (this.autoRefresh && this.store.getAuthzToken()) {
      this.scheduleRefresh()
    }
  }

  // ── Auth flow ───────────────────────────────────────────────────────

  /**
   * Resolve authorization: send IdP token to backend, get workspace list.
   * Call without workspace_id to discover workspaces, or use selectWorkspace() directly.
   */
  async resolve(idpToken: string, provider: string): Promise<AuthzResolveResponse> {
    const res = await fetch(`${this.backendUrl}/auth/resolve`, {
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

  /**
   * Select workspace and store both tokens.
   * Calls /auth/resolve with workspace_id, stores idp + authz tokens.
   */
  async selectWorkspace(idpToken: string, provider: string, workspaceId: string): Promise<void> {
    const res = await fetch(`${this.backendUrl}/auth/resolve`, {
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
      throw new Error((body as Record<string, string>).detail || `Token exchange failed`)
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

  get isAuthenticated(): boolean {
    const token = this.store.getAuthzToken()
    return !!token && !isTokenExpired(token)
  }

  /** Get dual-token headers for API calls. */
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

  /** Fetch with automatic dual headers and 401→re-resolve→retry. */
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

  /** Fetch JSON with automatic dual headers, 401 retry, and response parsing. */
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

  /** Re-resolve authz token using stored IdP token + provider + workspace. */
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
      // IdP token likely expired — user needs to re-authenticate
      this.store.clear()
      this.clearRefreshTimer()
      this.notify()
      return false
    }
  }

  // ── Events ────────────────────────────────────────────────────────

  onAuthStateChange(cb: AuthStateListener): () => void {
    this.listeners.add(cb)
    return () => { this.listeners.delete(cb) }
  }

  // ── Cleanup ───────────────────────────────────────────────────────

  logout(): void {
    this.store.clear()
    this.clearRefreshTimer()
    this.notify()
  }

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
```

**Step 4: Run test to verify it passes**

Run: `cd sdks/js && npx vitest run src/__tests__/authz-client.test.ts`
Expected: PASS (all 12 tests)

**Step 5: Commit**

```bash
git add sdks/js/src/authz-client.ts sdks/js/src/__tests__/authz-client.test.ts
git commit -m "feat(js-sdk): add SentinelAuthz client for dual-token auth"
```

---

## Task 4: Update JS SDK Exports

**Files:**
- Modify: `sdks/js/src/index.ts`

**Step 1: Add authz exports to index.ts**

Add to the existing `sdks/js/src/index.ts`:

```ts
// After existing exports:
export { SentinelAuthz } from './authz-client'
export { AuthzLocalStorageStore, AuthzMemoryStore } from './authz-storage'

// Add to the type exports:
export type {
  SentinelAuthzConfig,
  AuthzTokenStore,
  AuthzResolveResponse,
  AuthzUserInfo,
  AuthzWorkspaceOption,
  AuthzWorkspaceInfo,
} from './authz-types'
```

**Step 2: Run all JS SDK tests to verify nothing breaks**

Run: `cd sdks/js && npx vitest run`
Expected: All tests PASS (existing + new)

**Step 3: Build to verify exports resolve**

Run: `cd sdks/js && npx tsup`
Expected: Clean build, no errors

**Step 4: Commit**

```bash
git add sdks/js/src/index.ts
git commit -m "feat(js-sdk): export authz client and types from package entry"
```

---

## Task 5: React AuthzProvider (`@sentinel-auth/react`)

**Files:**
- Create: `sdks/react/src/authz-provider.tsx`
- Create: `sdks/react/src/authz-hooks.ts`
- Create: `sdks/react/src/authz-guard.tsx`
- Modify: `sdks/react/src/index.ts`

**Step 1: Create AuthzProvider**

```tsx
// sdks/react/src/authz-provider.tsx
import {
  createContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import {
  SentinelAuthz,
  type SentinelAuthzConfig,
  type SentinelUser,
  type AuthzResolveResponse,
} from '@sentinel-auth/js'

export interface AuthzContextValue {
  client: SentinelAuthz
  user: SentinelUser | null
  isLoading: boolean
  isAuthenticated: boolean
  resolve(idpToken: string, provider: string): Promise<AuthzResolveResponse>
  selectWorkspace(idpToken: string, provider: string, workspaceId: string): Promise<void>
  logout(): void
  fetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response>
  fetchJson: <T>(input: RequestInfo | URL, init?: RequestInit) => Promise<T>
}

const AuthzContext = createContext<AuthzContextValue | null>(null)

export interface AuthzProviderProps {
  config?: SentinelAuthzConfig
  client?: SentinelAuthz
  children: ReactNode
}

export function AuthzProvider({
  config,
  client: externalClient,
  children,
}: AuthzProviderProps) {
  const clientRef = useRef<SentinelAuthz | null>(externalClient ?? null)
  if (!clientRef.current) {
    if (!config) throw new Error('AuthzProvider requires either config or client prop')
    clientRef.current = new SentinelAuthz(config)
  }
  const client = clientRef.current
  const ownsClient = !externalClient

  const [user, setUser] = useState<SentinelUser | null>(() => client.getUser())
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    setUser(client.getUser())
    setIsLoading(false)

    const unsub = client.onAuthStateChange((u) => {
      setUser(u)
    })

    return () => {
      unsub()
      if (ownsClient) client.destroy()
    }
  }, [client, ownsClient])

  const value: AuthzContextValue = {
    client,
    user,
    isLoading,
    isAuthenticated: user !== null,
    resolve: (idpToken, provider) => client.resolve(idpToken, provider),
    selectWorkspace: (idpToken, provider, workspaceId) =>
      client.selectWorkspace(idpToken, provider, workspaceId),
    logout: () => client.logout(),
    fetch: (input, init) => client.fetch(input, init),
    fetchJson: <T,>(input: RequestInfo | URL, init?: RequestInit) =>
      client.fetchJson<T>(input, init),
  }

  return (
    <AuthzContext.Provider value={value}>
      {children}
    </AuthzContext.Provider>
  )
}

export { AuthzContext }
```

**Step 2: Create authz hooks**

```ts
// sdks/react/src/authz-hooks.ts
import { useContext } from 'react'
import type { SentinelUser, WorkspaceRole } from '@sentinel-auth/js'
import { AuthzContext, type AuthzContextValue } from './authz-provider'

const ROLE_HIERARCHY: WorkspaceRole[] = ['viewer', 'editor', 'admin', 'owner']

export function useAuthz(): AuthzContextValue {
  const ctx = useContext(AuthzContext)
  if (!ctx) {
    throw new Error('useAuthz must be used within an AuthzProvider')
  }
  return ctx
}

export function useAuthzUser(): SentinelUser {
  const { user } = useAuthz()
  if (!user) {
    throw new Error('useAuthzUser: no authenticated user')
  }
  return user
}

export function useAuthzHasRole(minimum: WorkspaceRole): boolean {
  const { user } = useAuthz()
  if (!user) return false
  const userLevel = ROLE_HIERARCHY.indexOf(user.workspaceRole)
  const requiredLevel = ROLE_HIERARCHY.indexOf(minimum)
  if (requiredLevel === -1) return false
  return userLevel >= requiredLevel
}

export function useAuthzFetch(): (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response> {
  const { fetch: authzFetch } = useAuthz()
  return authzFetch
}
```

**Step 3: Create AuthzGuard**

```tsx
// sdks/react/src/authz-guard.tsx
import type { ReactNode } from 'react'
import { useAuthz } from './authz-hooks'

export interface AuthzGuardProps {
  children: ReactNode
  fallback: ReactNode
  loading?: ReactNode
}

export function AuthzGuard({ children, fallback, loading = null }: AuthzGuardProps) {
  const { isAuthenticated, isLoading } = useAuthz()

  if (isLoading) return <>{loading}</>
  if (!isAuthenticated) return <>{fallback}</>
  return <>{children}</>
}
```

**Step 4: Update React index.ts with authz exports**

Add to existing `sdks/react/src/index.ts`:

```ts
export { AuthzProvider, AuthzContext, type AuthzContextValue, type AuthzProviderProps } from './authz-provider'
export { useAuthz, useAuthzUser, useAuthzHasRole, useAuthzFetch } from './authz-hooks'
export { AuthzGuard, type AuthzGuardProps } from './authz-guard'

// Add to re-exported types from @sentinel-auth/js:
export type {
  SentinelAuthzConfig,
  AuthzTokenStore,
  AuthzResolveResponse,
} from '@sentinel-auth/js'
```

**Step 5: Build to verify exports**

Run: `cd sdks/react && npx tsup`
Expected: Clean build

**Step 6: Commit**

```bash
git add sdks/react/src/authz-provider.tsx sdks/react/src/authz-hooks.ts sdks/react/src/authz-guard.tsx sdks/react/src/index.ts
git commit -m "feat(react-sdk): add AuthzProvider, useAuthz hooks, and AuthzGuard"
```

---

## Task 6: Next.js Authz Middleware (`@sentinel-auth/nextjs`)

**Files:**
- Create: `sdks/nextjs/src/authz-middleware.ts`
- Modify: `sdks/nextjs/tsup.config.ts`
- Modify: `sdks/nextjs/src/index.ts`

**Step 1: Create authz middleware**

```ts
// sdks/nextjs/src/authz-middleware.ts
import { type NextRequest, NextResponse } from 'next/server'
import { verifyToken } from '@sentinel-auth/js/server'

export interface SentinelAuthzMiddlewareConfig {
  /** Base URL of the Sentinel service. Derives /.well-known/jwks.json for authz token verification. */
  sentinelUrl: string
  /** JWKS URL for IdP token verification (e.g. Google's JWKS endpoint). */
  idpJwksUrl: string
  /** Paths that skip auth (e.g. ["/login", "/api/auth"]). */
  publicPaths?: string[]
  /** Redirect target for unauthenticated page requests. Defaults to "/login". */
  loginPath?: string
}

/**
 * Create a Next.js Edge Middleware that validates dual tokens (AuthZ mode).
 *
 * Validates:
 * 1. IdP token (Authorization: Bearer) — against IdP JWKS
 * 2. Authz token (X-Authz-Token) — against Sentinel JWKS
 * 3. idp_sub binding — authz token's idp_sub must match IdP token's sub
 *
 * Usage in `middleware.ts`:
 * ```ts
 * import { createSentinelAuthzMiddleware } from '@sentinel-auth/nextjs/authz-middleware'
 * export default createSentinelAuthzMiddleware({
 *   sentinelUrl: 'http://localhost:9003',
 *   idpJwksUrl: 'https://www.googleapis.com/oauth2/v3/certs',
 *   publicPaths: ['/login'],
 * })
 * export const config = { matcher: ['/((?!_next|favicon.ico).*)'] }
 * ```
 */
export function createSentinelAuthzMiddleware(config: SentinelAuthzMiddlewareConfig) {
  const {
    sentinelUrl,
    idpJwksUrl,
    publicPaths = [],
    loginPath = '/login',
  } = config

  const sentinelJwksUrl = `${sentinelUrl.replace(/\/+$/, '')}/.well-known/jwks.json`

  const SENTINEL_HEADERS = [
    'x-sentinel-user-id',
    'x-sentinel-email',
    'x-sentinel-name',
    'x-sentinel-workspace-id',
    'x-sentinel-workspace-slug',
    'x-sentinel-workspace-role',
    'x-sentinel-idp-sub',
  ] as const

  return async function middleware(req: NextRequest): Promise<NextResponse> {
    const { pathname } = req.nextUrl

    // Strip any client-sent x-sentinel-* headers to prevent spoofing
    const requestHeaders = new Headers(req.headers)
    for (const h of SENTINEL_HEADERS) {
      requestHeaders.delete(h)
    }

    // Skip public paths
    if (publicPaths.some((p) => pathname === p || pathname.startsWith(p + '/'))) {
      return NextResponse.next({ request: { headers: requestHeaders } })
    }

    // Extract IdP token from Authorization header
    const authHeader = req.headers.get('authorization')
    const idpToken = authHeader?.startsWith('Bearer ')
      ? authHeader.slice(7)
      : null

    // Extract authz token from X-Authz-Token header
    const authzToken = req.headers.get('x-authz-token')

    if (!idpToken || !authzToken) {
      return handleUnauthenticated(req, loginPath)
    }

    try {
      // Verify both tokens in parallel
      const [idpPayload, authzPayload] = await Promise.all([
        verifyToken(idpToken, { jwksUrl: idpJwksUrl, audience: undefined }),
        verifyToken(authzToken, { jwksUrl: sentinelJwksUrl, audience: 'sentinel:authz' }),
      ])

      // Check idp_sub binding: authz token's idp_sub must match IdP token's sub
      const authzClaims = authzPayload as Record<string, unknown>
      if (authzClaims.idp_sub !== idpPayload.sub) {
        return handleUnauthenticated(req, loginPath)
      }

      // Forward verified user info
      requestHeaders.set('x-sentinel-user-id', authzPayload.sub)
      requestHeaders.set('x-sentinel-email', authzPayload.email)
      requestHeaders.set('x-sentinel-name', authzPayload.name)
      requestHeaders.set('x-sentinel-workspace-id', authzPayload.wid)
      requestHeaders.set('x-sentinel-workspace-slug', authzPayload.wslug)
      requestHeaders.set('x-sentinel-workspace-role', authzPayload.wrole)
      requestHeaders.set('x-sentinel-idp-sub', String(authzClaims.idp_sub))

      return NextResponse.next({ request: { headers: requestHeaders } })
    } catch {
      return handleUnauthenticated(req, loginPath)
    }
  }
}

function handleUnauthenticated(
  req: NextRequest,
  loginPath: string,
): NextResponse {
  const isApiRoute = req.nextUrl.pathname.startsWith('/api/')
  if (isApiRoute) {
    return NextResponse.json({ detail: 'Unauthorized' }, { status: 401 })
  }
  const loginUrl = req.nextUrl.clone()
  loginUrl.pathname = loginPath
  return NextResponse.redirect(loginUrl)
}
```

**Step 2: Update tsup.config.ts to include authz-middleware entry point**

In `sdks/nextjs/tsup.config.ts`, add `'src/authz-middleware.ts'` to the entry array:

```ts
entry: ['src/index.ts', 'src/middleware.ts', 'src/server.ts', 'src/authz-middleware.ts'],
```

**Step 3: Add authz-middleware export to package.json**

In `sdks/nextjs/package.json`, add to the `exports` field:

```json
"./authz-middleware": {
  "types": "./dist/authz-middleware.d.ts",
  "import": "./dist/authz-middleware.js",
  "require": "./dist/authz-middleware.cjs"
}
```

**Step 4: Update nextjs/src/index.ts to re-export authz React components**

Add to existing `sdks/nextjs/src/index.ts`:

```ts
export {
  AuthzProvider,
  useAuthz,
  useAuthzUser,
  useAuthzHasRole,
  useAuthzFetch,
  AuthzGuard,
} from '@sentinel-auth/react'

export type {
  AuthzProviderProps,
  AuthzContextValue,
  AuthzGuardProps,
  SentinelAuthzConfig,
  AuthzTokenStore,
  AuthzResolveResponse,
} from '@sentinel-auth/react'
```

**Step 5: Build to verify all entry points**

Run: `cd sdks/nextjs && npx tsup`
Expected: Clean build with 4 entry points

**Step 6: Commit**

```bash
git add sdks/nextjs/src/authz-middleware.ts sdks/nextjs/tsup.config.ts sdks/nextjs/package.json sdks/nextjs/src/index.ts
git commit -m "feat(nextjs-sdk): add dual-token authz middleware and re-export authz components"
```

---

## Task 7: Demo AuthZ Backend — Add `/auth/resolve` Proxy Endpoint

**Files:**
- Modify: `demo-authz/backend/src/routes.py`

**Step 1: Add the proxy endpoint**

Add a new `/auth/resolve` route to `demo-authz/backend/src/routes.py` that proxies to Sentinel's `/authz/resolve`. This endpoint is **excluded** from the AuthzMiddleware (since the user doesn't have an authz token yet).

In `demo-authz/backend/src/main.py`, add `/auth/resolve` to exclude_paths:

```python
sentinel.protect(app, exclude_paths=["/health", "/docs", "/openapi.json", "/redoc", "/auth/resolve"])
```

In `demo-authz/backend/src/routes.py`, add:

```python
from pydantic import BaseModel as PydanticBaseModel


class ResolveRequest(PydanticBaseModel):
    idp_token: str
    provider: str
    workspace_id: str | None = None


@router.post("/auth/resolve")
async def auth_resolve(body: ResolveRequest):
    """Proxy to Sentinel's /authz/resolve. Adds service key server-side."""
    result = await sentinel.authz.resolve(
        idp_token=body.idp_token,
        provider=body.provider,
        workspace_id=uuid.UUID(body.workspace_id) if body.workspace_id else None,
    )
    return result
```

**Step 2: Verify the demo backend still starts**

Run: `cd demo-authz/backend && uv run python -c "from src.main import app; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add demo-authz/backend/src/routes.py demo-authz/backend/src/main.py
git commit -m "feat(demo-authz): add /auth/resolve proxy endpoint for frontend SDK"
```

---

## Task 8: Demo AuthZ Frontend — React App with Google Sign-In + AuthzProvider

**Files:**
- Create: `demo-authz/frontend/package.json`
- Create: `demo-authz/frontend/index.html`
- Create: `demo-authz/frontend/vite.config.ts`
- Create: `demo-authz/frontend/tsconfig.json`
- Create: `demo-authz/frontend/src/main.tsx`
- Create: `demo-authz/frontend/src/App.tsx`
- Create: `demo-authz/frontend/src/components/Login.tsx`
- Create: `demo-authz/frontend/src/components/WorkspacePicker.tsx`
- Create: `demo-authz/frontend/src/components/Notes.tsx`

**Step 1: Create package.json**

```json
{
  "name": "demo-authz-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "@react-oauth/google": "^0.12.0",
    "@sentinel-auth/js": "file:../../sdks/js",
    "@sentinel-auth/react": "file:../../sdks/react"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.0.0",
    "typescript": "^5.5.0",
    "vite": "^6.0.0"
  }
}
```

**Step 2: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Team Notes — AuthZ Mode Demo</title>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.tsx"></script>
</body>
</html>
```

**Step 3: Create vite.config.ts**

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 5174 },
})
```

**Step 4: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "dist"
  },
  "include": ["src"]
}
```

**Step 5: Create src/main.tsx**

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { GoogleOAuthProvider } from '@react-oauth/google'
import { AuthzProvider } from '@sentinel-auth/react'
import { App } from './App'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:9200'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <AuthzProvider config={{ backendUrl: BACKEND_URL }}>
        <App />
      </AuthzProvider>
    </GoogleOAuthProvider>
  </StrictMode>,
)
```

**Step 6: Create src/App.tsx**

```tsx
import { useState } from 'react'
import { useAuthz } from '@sentinel-auth/react'
import type { AuthzWorkspaceOption } from '@sentinel-auth/js'
import { Login } from './components/Login'
import { WorkspacePicker } from './components/WorkspacePicker'
import { Notes } from './components/Notes'

export function App() {
  const { isAuthenticated, user, logout } = useAuthz()
  const [workspaces, setWorkspaces] = useState<AuthzWorkspaceOption[] | null>(null)
  const [idpToken, setIdpToken] = useState<string | null>(null)

  if (isAuthenticated && user) {
    return (
      <div style={{ maxWidth: 600, margin: '2rem auto', fontFamily: 'system-ui' }}>
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div>
            <strong>{user.name}</strong> — {user.workspaceSlug} ({user.workspaceRole})
          </div>
          <button onClick={logout}>Logout</button>
        </header>
        <Notes />
      </div>
    )
  }

  if (workspaces && idpToken) {
    return (
      <WorkspacePicker
        workspaces={workspaces}
        idpToken={idpToken}
        onBack={() => { setWorkspaces(null); setIdpToken(null) }}
      />
    )
  }

  return (
    <Login
      onResolved={(token, ws) => {
        setIdpToken(token)
        setWorkspaces(ws)
      }}
    />
  )
}
```

**Step 7: Create src/components/Login.tsx**

```tsx
import { useGoogleLogin } from '@react-oauth/google'
import { useAuthz } from '@sentinel-auth/react'
import type { AuthzWorkspaceOption } from '@sentinel-auth/js'

interface LoginProps {
  onResolved: (idpToken: string, workspaces: AuthzWorkspaceOption[]) => void
}

export function Login({ onResolved }: LoginProps) {
  const { resolve, selectWorkspace } = useAuthz()

  const login = useGoogleLogin({
    flow: 'implicit',
    onSuccess: async (response) => {
      // Google implicit flow returns access_token; for ID token we need to
      // use the 'id_token' response type. The @react-oauth/google library
      // provides the credential (ID token) via the CredentialResponse.
      // For the implicit flow, we get an access_token which won't work
      // as an IdP token for Sentinel. We'll use the authorization code flow
      // or the One Tap approach instead.
    },
  })

  // Use Google One Tap / Sign In button for ID token
  const handleGoogleSignIn = async (credential: string) => {
    try {
      const result = await resolve(credential, 'google')

      if (result.workspaces && result.workspaces.length > 0) {
        if (result.workspaces.length === 1) {
          // Auto-select single workspace
          await selectWorkspace(credential, 'google', result.workspaces[0].id)
        } else {
          onResolved(credential, result.workspaces)
        }
      }
    } catch (err) {
      console.error('Auth resolve failed:', err)
    }
  }

  return (
    <div style={{ maxWidth: 400, margin: '4rem auto', textAlign: 'center', fontFamily: 'system-ui' }}>
      <h1>Team Notes</h1>
      <p style={{ color: '#666' }}>AuthZ Mode Demo — Sign in with Google</p>
      <div id="google-signin-button" style={{ display: 'inline-block', marginTop: '1rem' }}>
        {/* @react-oauth/google GoogleLogin component provides the credential (ID token) */}
      </div>
      <GoogleSignInButton onCredential={handleGoogleSignIn} />
    </div>
  )
}

function GoogleSignInButton({ onCredential }: { onCredential: (credential: string) => void }) {
  // Using the declarative GoogleLogin component from @react-oauth/google
  // which returns a credential (ID token) on success
  const { GoogleLogin } = require('@react-oauth/google')
  return (
    <GoogleLogin
      onSuccess={(response: { credential?: string }) => {
        if (response.credential) {
          onCredential(response.credential)
        }
      }}
      onError={() => console.error('Google Sign-In failed')}
    />
  )
}
```

**Step 8: Create src/components/WorkspacePicker.tsx**

```tsx
import { useAuthz } from '@sentinel-auth/react'
import type { AuthzWorkspaceOption } from '@sentinel-auth/js'

interface WorkspacePickerProps {
  workspaces: AuthzWorkspaceOption[]
  idpToken: string
  onBack: () => void
}

export function WorkspacePicker({ workspaces, idpToken, onBack }: WorkspacePickerProps) {
  const { selectWorkspace } = useAuthz()

  const handleSelect = async (ws: AuthzWorkspaceOption) => {
    await selectWorkspace(idpToken, 'google', ws.id)
  }

  return (
    <div style={{ maxWidth: 400, margin: '4rem auto', fontFamily: 'system-ui' }}>
      <h2>Select Workspace</h2>
      <ul style={{ listStyle: 'none', padding: 0 }}>
        {workspaces.map((ws) => (
          <li key={ws.id} style={{ marginBottom: '0.5rem' }}>
            <button
              onClick={() => handleSelect(ws)}
              style={{ width: '100%', padding: '0.75rem', textAlign: 'left', cursor: 'pointer' }}
            >
              <strong>{ws.name}</strong> <span style={{ color: '#666' }}>({ws.role})</span>
            </button>
          </li>
        ))}
      </ul>
      <button onClick={onBack} style={{ marginTop: '1rem' }}>Back</button>
    </div>
  )
}
```

**Step 9: Create src/components/Notes.tsx**

```tsx
import { useEffect, useState } from 'react'
import { useAuthz } from '@sentinel-auth/react'

interface Note {
  id: string
  title: string
  content: string
  owner_name: string
}

export function Notes() {
  const { fetchJson } = useAuthz()
  const [notes, setNotes] = useState<Note[]>([])
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')

  const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://localhost:9200'

  const loadNotes = async () => {
    try {
      const data = await fetchJson<Note[]>(`${BACKEND}/notes`)
      setNotes(data)
    } catch (err) {
      console.error('Failed to load notes:', err)
    }
  }

  useEffect(() => {
    loadNotes()
  }, [])

  const createNote = async () => {
    if (!title.trim()) return
    try {
      await fetchJson(`${BACKEND}/notes`, {
        method: 'POST',
        body: JSON.stringify({ title, content }),
      })
      setTitle('')
      setContent('')
      await loadNotes()
    } catch (err) {
      console.error('Failed to create note:', err)
    }
  }

  return (
    <div>
      <h2>Notes</h2>

      <div style={{ marginBottom: '1.5rem', padding: '1rem', border: '1px solid #ddd', borderRadius: 4 }}>
        <input
          placeholder="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          style={{ display: 'block', width: '100%', marginBottom: '0.5rem', padding: '0.5rem' }}
        />
        <textarea
          placeholder="Content"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          style={{ display: 'block', width: '100%', marginBottom: '0.5rem', padding: '0.5rem' }}
          rows={3}
        />
        <button onClick={createNote}>Create Note</button>
      </div>

      {notes.length === 0 ? (
        <p style={{ color: '#666' }}>No notes yet.</p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {notes.map((note) => (
            <li key={note.id} style={{ marginBottom: '1rem', padding: '1rem', border: '1px solid #eee', borderRadius: 4 }}>
              <strong>{note.title}</strong>
              <p>{note.content}</p>
              <small style={{ color: '#999' }}>by {note.owner_name}</small>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
```

**Step 10: Install dependencies and verify it builds**

```bash
cd demo-authz/frontend && npm install && npx tsc --noEmit
```

**Step 11: Update demo-authz README with frontend instructions**

Add frontend section to `demo-authz/README.md`.

**Step 12: Commit**

```bash
git add demo-authz/frontend/
git commit -m "feat(demo-authz): add React frontend with Google Sign-In + AuthzProvider"
```

---

## Task 9: Verify All SDK Tests and Builds

**Step 1: Run all JS SDK tests**

```bash
cd sdks/js && npx vitest run
```
Expected: All tests pass (existing proxy-mode + new authz tests)

**Step 2: Build all three packages**

```bash
cd sdks/js && npx tsup
cd sdks/react && npx tsup
cd sdks/nextjs && npx tsup
```
Expected: All three build cleanly

**Step 3: Run Python service tests**

```bash
cd service && uv run pytest tests/ -x
```
Expected: All tests pass

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: verify all SDK tests and builds pass"
```
