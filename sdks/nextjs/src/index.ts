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

// Authz-mode components, hooks, and types
export {
  AuthzProvider,
  useAuthz,
  useAuthzUser,
  useAuthzHasRole,
  useAuthzFetch,
  AuthzGuard,
  AuthzCallback,
} from '@sentinel-auth/react'

export type {
  AuthzProviderProps,
  AuthzContextValue,
  AuthzGuardProps,
  AuthzCallbackProps,
  AuthzWorkspaceSelectorProps,
  SentinelAuthzConfig,
  AuthzTokenStore,
  AuthzResolveResponse,
} from '@sentinel-auth/react'
