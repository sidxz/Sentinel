// Browser + types entry point
export { SentinelAuth } from './client'
export { generateCodeVerifier, deriveCodeChallenge } from './pkce'
export { LocalStorageStore, SessionStorageStore, MemoryStore } from './storage'
export { parseJwt, isTokenExpired, tokenToUser } from './jwt-utils'

export type {
  SentinelConfig,
  TokenStore,
  TokenResponse,
  WorkspaceOption,
  SentinelUser,
  WorkspaceRole,
  JWTPayload,
  PermissionCheck,
  PermissionResult,
  RegisterResourceRequest,
  ShareRequest,
  AccessibleResult,
  ActionDefinition,
  VerifyOptions,
} from './types'
