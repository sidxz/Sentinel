export { SentinelAuthProvider, type SentinelAuthContextValue, type SentinelAuthProviderProps } from './provider'
export { useAuth, useUser, useHasRole, useAuthFetch } from './hooks'
export { AuthGuard, type AuthGuardProps } from './auth-guard'
export { AuthCallback, type AuthCallbackProps, type WorkspaceSelectorProps } from './callback'

// Re-export commonly used types from @sentinel-auth/js
export type {
  SentinelConfig,
  SentinelUser,
  WorkspaceOption,
  WorkspaceRole,
} from '@sentinel-auth/js'
