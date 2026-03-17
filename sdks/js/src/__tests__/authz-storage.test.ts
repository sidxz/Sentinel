import { describe, it, expect, beforeEach, vi } from 'vitest'
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
    expect(store.getUserIdentity()).toBeNull()
  })

  it('stores and retrieves all tokens', () => {
    store.setTokens('idp-jwt', 'authz-jwt', 'google', 'ws-1')
    expect(store.getIdpToken()).toBe('idp-jwt')
    expect(store.getAuthzToken()).toBe('authz-jwt')
    expect(store.getProvider()).toBe('google')
    expect(store.getWorkspaceId()).toBe('ws-1')
  })

  it('stores and retrieves user identity', () => {
    store.setUserIdentity({ email: 'alice@acme.com', name: 'Alice' })
    expect(store.getUserIdentity()).toEqual({ email: 'alice@acme.com', name: 'Alice' })
  })

  it('clear removes all tokens and identity', () => {
    store.setTokens('idp-jwt', 'authz-jwt', 'google', 'ws-1')
    store.setUserIdentity({ email: 'alice@acme.com', name: 'Alice' })
    store.clear()
    expect(store.getIdpToken()).toBeNull()
    expect(store.getAuthzToken()).toBeNull()
    expect(store.getProvider()).toBeNull()
    expect(store.getWorkspaceId()).toBeNull()
    expect(store.getUserIdentity()).toBeNull()
  })
})

describe('AuthzLocalStorageStore', () => {
  let store: AuthzLocalStorageStore
  let mockStorage: Record<string, string>

  beforeEach(() => {
    mockStorage = {}
    const storageMock = {
      getItem: vi.fn((key: string) => mockStorage[key] ?? null),
      setItem: vi.fn((key: string, value: string) => { mockStorage[key] = value }),
      removeItem: vi.fn((key: string) => { delete mockStorage[key] }),
    }
    vi.stubGlobal('localStorage', storageMock)
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

  it('stores and retrieves user identity', () => {
    store.setUserIdentity({ email: 'alice@acme.com', name: 'Alice' })
    expect(store.getUserIdentity()).toEqual({ email: 'alice@acme.com', name: 'Alice' })
    expect(localStorage.setItem).toHaveBeenCalledWith('sentinel_user_email', 'alice@acme.com')
    expect(localStorage.setItem).toHaveBeenCalledWith('sentinel_user_name', 'Alice')
  })

  it('getUserIdentity returns null when not set', () => {
    expect(store.getUserIdentity()).toBeNull()
  })

  it('clear removes from localStorage', () => {
    store.setTokens('idp-jwt', 'authz-jwt', 'google', 'ws-1')
    store.setUserIdentity({ email: 'alice@acme.com', name: 'Alice' })
    store.clear()
    expect(localStorage.getItem('sentinel_idp_token')).toBeNull()
    expect(localStorage.getItem('sentinel_authz_token')).toBeNull()
    expect(localStorage.getItem('sentinel_user_email')).toBeNull()
    expect(localStorage.getItem('sentinel_user_name')).toBeNull()
  })

  it('uses sentinel_ prefix in localStorage keys', () => {
    store.setTokens('idp-jwt', 'authz-jwt', 'google', 'ws-1')
    expect(localStorage.setItem).toHaveBeenCalledWith('sentinel_idp_token', 'idp-jwt')
    expect(localStorage.setItem).toHaveBeenCalledWith('sentinel_authz_token', 'authz-jwt')
    expect(localStorage.setItem).toHaveBeenCalledWith('sentinel_idp_provider', 'google')
    expect(localStorage.setItem).toHaveBeenCalledWith('sentinel_workspace_id', 'ws-1')
  })
})
