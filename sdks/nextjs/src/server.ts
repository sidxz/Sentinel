import { headers } from 'next/headers'
import type { SentinelUser, WorkspaceRole } from '@sentinel-auth/js'

/**
 * Read the current Sentinel user from request headers (set by middleware).
 * Returns null if the middleware did not set user headers.
 */
export async function getUser(): Promise<SentinelUser | null> {
  const h = await headers()
  const userId = h.get('x-sentinel-user-id')
  if (!userId) return null

  return {
    userId,
    email: h.get('x-sentinel-email') ?? '',
    name: h.get('x-sentinel-name') ?? '',
    workspaceId: h.get('x-sentinel-workspace-id') ?? '',
    workspaceSlug: h.get('x-sentinel-workspace-slug') ?? '',
    workspaceRole: (h.get('x-sentinel-workspace-role') ?? 'viewer') as WorkspaceRole,
    groups: [],
  }
}

/**
 * Require an authenticated Sentinel user. Throws a 401 error if not found.
 */
export async function requireUser(): Promise<SentinelUser> {
  const user = await getUser()
  if (!user) {
    throw new Error('Unauthorized')
  }
  return user
}

/**
 * Get the raw JWT token from the Authorization header.
 */
export async function getToken(): Promise<string | null> {
  const h = await headers()
  const auth = h.get('authorization')
  if (!auth?.startsWith('Bearer ')) return null
  return auth.slice(7)
}

/**
 * HOC for Route Handlers that require authentication.
 * Extracts user from headers and passes to handler.
 */
export function withAuth<T>(
  handler: (req: Request, user: SentinelUser) => Promise<T>,
): (req: Request) => Promise<T> {
  return async (req: Request) => {
    const user = await requireUser()
    return handler(req, user)
  }
}
