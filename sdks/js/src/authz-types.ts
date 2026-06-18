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
   *  Used by the browser only to DISCOVER workspaces for an IdP token. */
  sentinelUrl: string
  /**
   * URL of YOUR backend's mint endpoint. Required.
   *
   * The browser calls this endpoint (not Sentinel directly) to exchange an IdP
   * token + workspace_id for a Sentinel authz token. Your backend is expected
   * to hold the Sentinel service key and forward the request to
   * ``POST {sentinelUrl}/authz/resolve`` with ``X-Service-Key``.
   *
   * Rationale: minting an authz token is credential issuance and must be
   * gated by server-to-server trust, not by browser Origin matching. Without
   * this indirection any XSS could mint fresh authz tokens as long as the
   * IdP token remained valid (~1 hour for Google).
   *
   * Request body (same as /authz/resolve): ``{idp_token, provider, workspace_id, nonce?}``
   * Expected response: same shape as ``AuthzResolveResponse`` (``authz_token`` included).
   *
   * Example: ``"/api/auth/mint"``.
   */
  mintEndpoint: string
  /** IdP configurations keyed by provider name (e.g. { google: IdpConfigs.google('client-id') }). */
  idps?: Record<string, IdpConfig>
  /** OAuth redirect URI. Defaults to `${window.location.origin}/auth/callback`. */
  redirectUri?: string
  /** Token storage backend. Defaults to in-memory (AuthzMemoryStore). Pass `new AuthzLocalStorageStore()` to persist across page reloads. */
  storage?: AuthzTokenStore
  /** Automatically refresh authz token before expiry. Defaults to true. */
  autoRefresh?: boolean
  /** Seconds before authz token expiry to trigger refresh. Defaults to 30. */
  refreshBuffer?: number
}

export interface UserIdentity {
  email: string
  name: string
}

/**
 * Derived auth state for AuthZ mode.
 *
 * - ``authenticated``   — a valid authz token AND a usable IdP token are present;
 *                          requests can be made.
 * - ``needs_reauth``    — a valid authz token exists but the IdP token is gone
 *                          (e.g. after a page reload, where the IdP token is
 *                          memory-only). Requests cannot be authenticated until
 *                          the user re-auths with the IdP (see ``silentLogin``).
 * - ``unauthenticated`` — no usable authz token (absent or expired).
 */
export type AuthState = 'authenticated' | 'needs_reauth' | 'unauthenticated'

/** Outcome of {@link SentinelAuthz.handleCallback}. */
export type AuthzCallbackResult =
  | { status: 'success'; idpToken: string; provider: string; returnTo: string | null }
  | { status: 'silent_failed'; error: string; provider: string | null; returnTo: string | null }

export interface AuthzTokenStore {
  getIdpToken(): string | null
  getAuthzToken(): string | null
  getProvider(): string | null
  getWorkspaceId(): string | null
  getUserIdentity(): UserIdentity | null
  setTokens(idpToken: string, authzToken: string, provider: string, workspaceId: string): void
  setUserIdentity(identity: UserIdentity): void
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

// ── Workspace & group types for SentinelAuthz helpers ───────────────

export interface WorkspaceMember {
  user_id: string
  email: string
  name: string
  avatar_url: string | null
  role: WorkspaceRole
  joined_at: string
}

export interface GroupInfo {
  id: string
  workspace_id: string
  name: string
  description: string | null
  created_by: string
  created_at: string
}

export interface GroupMemberInfo {
  user_id: string
  email: string
  name: string
  added_at: string
}

export interface UserProfile {
  id: string
  email: string
  name: string
  avatar_url: string | null
  is_active: boolean
  created_at: string
}

export { SentinelUser, WorkspaceRole }
