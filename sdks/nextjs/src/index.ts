'use client'
export {
  SentinelAuthProvider,
  useAuth,
  useUser,
  useHasRole,
  useAuthFetch,
  AuthGuard,
  AuthCallback,
} from '@sentinel-auth/react'

export type {
  SentinelAuthProviderProps,
  SentinelAuthContextValue,
  AuthGuardProps,
  AuthCallbackProps,
  WorkspaceSelectorProps,
  SentinelConfig,
  SentinelUser,
  WorkspaceOption,
  WorkspaceRole,
} from '@sentinel-auth/react'
