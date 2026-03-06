import { type NextRequest, NextResponse } from 'next/server'
import { verifyToken, payloadToUser } from '@sentinel-auth/js/server'

export interface SentinelMiddlewareConfig {
  /** URL to the JWKS endpoint. */
  jwksUrl: string
  /** Paths that skip auth (e.g. ["/login", "/auth/callback"]). */
  publicPaths?: string[]
  /** Redirect target for unauthenticated page requests. Defaults to "/login". */
  loginPath?: string
  /** Expected audience. Defaults to "sentinel:access". */
  audience?: string
  /** Optional workspace ID allowlist. */
  allowedWorkspaces?: string[]
}

/**
 * Create a Next.js Edge Middleware that verifies Sentinel JWTs.
 *
 * Usage in `middleware.ts`:
 * ```ts
 * import { createSentinelMiddleware } from '@sentinel-auth/nextjs/middleware'
 * export default createSentinelMiddleware({
 *   jwksUrl: 'http://localhost:9003/.well-known/jwks.json',
 *   publicPaths: ['/login', '/auth/callback'],
 * })
 * export const config = { matcher: ['/((?!_next|favicon.ico).*)'] }
 * ```
 */
export function createSentinelMiddleware(config: SentinelMiddlewareConfig) {
  const {
    jwksUrl,
    publicPaths = [],
    loginPath = '/login',
    audience = 'sentinel:access',
    allowedWorkspaces,
  } = config

  // Warn if JWKS URL is plain HTTP on a non-localhost host
  try {
    const parsed = new URL(jwksUrl)
    const safe = new Set(['localhost', '127.0.0.1', '::1'])
    if (parsed.protocol === 'http:' && !safe.has(parsed.hostname)) {
      console.warn(
        `[sentinel-auth] (NextMiddleware) Fetching JWKS over plain HTTP from ${parsed.hostname}. ` +
          'Use HTTPS in production to protect token verification.',
      )
    }
  } catch { /* invalid URL — let verifyToken handle it */ }

  return async function middleware(req: NextRequest): Promise<NextResponse> {
    const { pathname } = req.nextUrl

    // Skip public paths
    if (publicPaths.some((p) => pathname === p || pathname.startsWith(p + '/'))) {
      return NextResponse.next()
    }

    // Extract token from Authorization header or cookie
    const authHeader = req.headers.get('authorization')
    const token = authHeader?.startsWith('Bearer ')
      ? authHeader.slice(7)
      : req.cookies.get('sentinel_access_token')?.value

    if (!token) {
      return handleUnauthenticated(req, loginPath)
    }

    try {
      const payload = await verifyToken(token, { jwksUrl, audience })
      const user = payloadToUser(payload)

      // Check workspace allowlist
      if (allowedWorkspaces && !allowedWorkspaces.includes(user.workspaceId)) {
        return handleUnauthenticated(req, loginPath)
      }

      // Forward user info in headers for server components/route handlers
      const response = NextResponse.next()
      response.headers.set('x-sentinel-user-id', user.userId)
      response.headers.set('x-sentinel-email', user.email)
      response.headers.set('x-sentinel-name', user.name)
      response.headers.set('x-sentinel-workspace-id', user.workspaceId)
      response.headers.set('x-sentinel-workspace-slug', user.workspaceSlug)
      response.headers.set('x-sentinel-workspace-role', user.workspaceRole)
      return response
    } catch {
      return handleUnauthenticated(req, loginPath)
    }
  }
}

function handleUnauthenticated(
  req: NextRequest,
  loginPath: string,
): NextResponse {
  const isApiRoute = req.nextUrl.pathname.startsWith('/api/')
  if (isApiRoute) {
    return NextResponse.json({ detail: 'Unauthorized' }, { status: 401 })
  }
  const loginUrl = req.nextUrl.clone()
  loginUrl.pathname = loginPath
  return NextResponse.redirect(loginUrl)
}
