import { useContext } from 'react'
import type { SentinelUser, WorkspaceRole } from '@sentinel-auth/js'
import { SentinelAuthContext, type SentinelAuthContextValue } from './provider'

const ROLE_HIERARCHY: WorkspaceRole[] = ['viewer', 'editor', 'admin', 'owner']

/** Access the full Sentinel auth context. Throws if used outside SentinelAuthProvider. */
export function useAuth(): SentinelAuthContextValue {
  const ctx = useContext(SentinelAuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within a SentinelAuthProvider')
  }
  return ctx
}

/** Get the current authenticated user. Throws if not authenticated. */
export function useUser(): SentinelUser {
  const { user } = useAuth()
  if (!user) {
    throw new Error('useUser: no authenticated user')
  }
  return user
}

/** Check if the current user has at least the given workspace role. */
export function useHasRole(minimum: WorkspaceRole): boolean {
  const { user } = useAuth()
  if (!user) return false
  const userLevel = ROLE_HIERARCHY.indexOf(user.workspaceRole)
  const requiredLevel = ROLE_HIERARCHY.indexOf(minimum)
  return userLevel >= requiredLevel
}

/** Shortcut to the auth-aware fetch. */
export function useAuthFetch(): (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response> {
  const { fetch: authFetch } = useAuth()
  return authFetch
}
