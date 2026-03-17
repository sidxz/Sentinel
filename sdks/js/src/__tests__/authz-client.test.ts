import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { SentinelAuthz } from '../authz-client'
import { AuthzMemoryStore } from '../authz-storage'

function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: 'RS256', typ: 'JWT' }))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  const body = btoa(JSON.stringify(payload))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  return `${header}.${body}.fake-signature`
}

const authzPayload = {
  sub: 'user-1',
  wid: 'ws-1',
  wslug: 'acme',
  wrole: 'editor',
  idp_sub: 'google|123',
  svc: 'notes',
  actions: ['notes:create'],
  aud: 'sentinel:authz',
  iss: 'sentinel',
  exp: Math.floor(Date.now() / 1000) + 300,
  iat: Math.floor(Date.now() / 1000),
  jti: 'jti-authz-1',
  type: 'authz',
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
      sentinelUrl: 'http://localhost:9003',
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
    expect(fetch).toHaveBeenCalledWith('http://localhost:9003/authz/resolve', {
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
    expect(fetch).toHaveBeenCalledWith('http://localhost:9003/authz/resolve', {
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
    expect(store.getUserIdentity()).toEqual({ email: 'alice@acme.com', name: 'Alice' })
    expect(listener).toHaveBeenCalledTimes(1)
    expect(listener.mock.calls[0][0]).not.toBeNull()
  })

  it('getUser returns user from authz token with cached identity', () => {
    const authzToken = makeJwt(authzPayload)
    store.setUserIdentity({ email: 'alice@acme.com', name: 'Alice' })
    store.setTokens('idp-token', authzToken, 'google', 'ws-1')
    const user = client.getUser()
    expect(user).not.toBeNull()
    expect(user!.userId).toBe('user-1')
    expect(user!.email).toBe('alice@acme.com')
    expect(user!.name).toBe('Alice')
    expect(user!.workspaceRole).toBe('editor')
    expect(user!.groups).toEqual([])
  })

  it('getUser returns empty strings for identity when not cached', () => {
    const authzToken = makeJwt(authzPayload)
    store.setTokens('idp-token', authzToken, 'google', 'ws-1')
    const user = client.getUser()
    expect(user).not.toBeNull()
    expect(user!.userId).toBe('user-1')
    expect(user!.email).toBe('')
    expect(user!.name).toBe('')
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
      .mockResolvedValueOnce(new Response('', { status: 401 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({
          ...selectResponse,
          authz_token: newAuthzToken,
        }), { status: 200 }),
      )
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
