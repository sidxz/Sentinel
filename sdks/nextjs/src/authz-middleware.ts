import { type NextRequest, NextResponse } from 'next/server'
import { createRemoteJWKSet, jwtVerify } from 'jose'
import { verifyToken } from '@sentinel-auth/js/server'

export interface SentinelAuthzMiddlewareConfig {
  /** Base URL of the Sentinel service. Derives /.well-known/jwks.json for authz token verification. */
  sentinelUrl: string
  /** JWKS URL for IdP token verification (e.g. Google's JWKS endpoint). */
  idpJwksUrl: string
  /** Paths that skip auth (e.g. ["/login", "/api/auth"]). */
  publicPaths?: string[]
  /** Redirect target for unauthenticated page requests. Defaults to "/login". */
  loginPath?: string
}

// Cache JWKS sets across invocations (Edge runtime module-scoped)
const jwksSets = new Map<string, ReturnType<typeof createRemoteJWKSet>>()

function getJWKS(url: string) {
  let jwks = jwksSets.get(url)
  if (!jwks) {
    jwks = createRemoteJWKSet(new URL(url))
    jwksSets.set(url, jwks)
  }
  return jwks
}

/**
 * Create a Next.js Edge Middleware that validates dual tokens (AuthZ mode).
 *
 * Validates:
 * 1. IdP token (Authorization: Bearer) — against IdP JWKS (signature only, no audience check)
 * 2. Authz token (X-Authz-Token) — against Sentinel JWKS (audience: sentinel:authz)
 * 3. idp_sub binding — authz token's idp_sub must match IdP token's sub
 *
 * Usage in `middleware.ts`:
 * ```ts
 * import { createSentinelAuthzMiddleware } from '@sentinel-auth/nextjs/authz-middleware'
 * export default createSentinelAuthzMiddleware({
 *   sentinelUrl: 'http://localhost:9003',
 *   idpJwksUrl: 'https://www.googleapis.com/oauth2/v3/certs',
 *   publicPaths: ['/login', '/auth/callback'],
 * })
 * export const config = { matcher: ['/((?!_next|favicon.ico).*)'] }
 * ```
 */
export function createSentinelAuthzMiddleware(config: SentinelAuthzMiddlewareConfig) {
  const {
    sentinelUrl,
    idpJwksUrl,
    publicPaths = [],
    loginPath = '/login',
  } = config

  const sentinelJwksUrl = `${sentinelUrl.replace(/\/+$/, '')}/.well-known/jwks.json`

  const SENTINEL_HEADERS = [
    'x-sentinel-user-id',
    'x-sentinel-email',
    'x-sentinel-name',
    'x-sentinel-workspace-id',
    'x-sentinel-workspace-slug',
    'x-sentinel-workspace-role',
    'x-sentinel-idp-sub',
  ] as const

  return async function middleware(req: NextRequest): Promise<NextResponse> {
    const { pathname } = req.nextUrl

    // Strip any client-sent x-sentinel-* headers to prevent spoofing.
    // This runs on ALL paths (public and protected) so that downstream
    // server components / route handlers can never see forged identity.
    const requestHeaders = new Headers(req.headers)
    for (const h of SENTINEL_HEADERS) {
      requestHeaders.delete(h)
    }

    // Skip public paths
    if (publicPaths.some((p) => pathname === p || pathname.startsWith(p + '/'))) {
      return NextResponse.next({ request: { headers: requestHeaders } })
    }

    // Extract IdP token from Authorization header
    const authHeader = req.headers.get('authorization')
    const idpToken = authHeader?.startsWith('Bearer ')
      ? authHeader.slice(7)
      : null

    // Extract authz token from X-Authz-Token header
    const authzToken = req.headers.get('x-authz-token')

    if (!idpToken || !authzToken) {
      return handleUnauthenticated(req, loginPath)
    }

    try {
      // Verify both tokens in parallel.
      // IdP token: verify signature only (no audience restriction — the IdP's
      //   audience is the app's OAuth client ID, not something we enforce here).
      // Authz token: verify signature + audience via Sentinel's verifyToken.
      const [idpResult, authzPayload] = await Promise.all([
        jwtVerify(idpToken, getJWKS(idpJwksUrl)),
        verifyToken(authzToken, { jwksUrl: sentinelJwksUrl, audience: 'sentinel:authz' }),
      ])

      const idpPayload = idpResult.payload

      // Check idp_sub binding: authz token's idp_sub must match IdP token's sub
      const authzClaims = authzPayload as unknown as Record<string, unknown>
      if (!idpPayload.sub || authzClaims.idp_sub !== idpPayload.sub) {
        return handleUnauthenticated(req, loginPath)
      }

      // Forward verified user info in request headers for server components / route handlers
      requestHeaders.set('x-sentinel-user-id', String(authzPayload.sub))
      requestHeaders.set('x-sentinel-email', String(authzPayload.email))
      requestHeaders.set('x-sentinel-name', String(authzPayload.name))
      requestHeaders.set('x-sentinel-workspace-id', String(authzPayload.wid))
      requestHeaders.set('x-sentinel-workspace-slug', String(authzPayload.wslug))
      requestHeaders.set('x-sentinel-workspace-role', String(authzPayload.wrole))
      requestHeaders.set('x-sentinel-idp-sub', String(authzClaims.idp_sub))

      return NextResponse.next({ request: { headers: requestHeaders } })
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
