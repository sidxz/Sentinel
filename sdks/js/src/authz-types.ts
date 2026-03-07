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
