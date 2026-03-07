import type { SentinelUser, WorkspaceRole } from './types'

/** Configuration for a specific IdP (Google, EntraID, etc.). */
export interface IdpConfig {
  /** OAuth client ID for this provider. */
  clientId: string
  /** OAuth authorization endpoint URL. */
  authorizationUrl: string
  /** Scopes to request. Defaults to ['openid', 'email', 'profile']. */
  scopes?: string[]
  /** OAuth response type. Defaults to 'id_token'. */
  responseType?: string
  /** Additional query parameters to include in the OAuth URL. */
  extraParams?: Record<string, string>
}

/** Well-known IdP configurations. */
export const IdpConfigs = {
  google: (clientId: string): IdpConfig => ({
    clientId,
    authorizationUrl: 'https://accounts.google.com/o/oauth2/v2/auth',
    scopes: ['openid', 'email', 'profile'],
    responseType: 'id_token',
  }),
  entraId: (clientId: string, tenantId: string): IdpConfig => ({
    clientId,
    authorizationUrl: `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/authorize`,
    scopes: ['openid', 'email', 'profile'],
    responseType: 'id_token',
  }),
} as const

export interface SentinelAuthzConfig {
  /** Base URL of the Sentinel service (e.g. "http://localhost:9003").
   *  Derives /authz/resolve for token exchange. */
  sentinelUrl: string
  /** IdP configurations keyed by provider name (e.g. { google: IdpConfigs.google('client-id') }). */
  idps?: Record<string, IdpConfig>
  /** OAuth redirect URI. Defaults to `${window.location.origin}/auth/callback`. */
  redirectUri?: string
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
