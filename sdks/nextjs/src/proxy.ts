/**
 * Reverse proxy for private-network Sentinel deployments.
 *
 * When Sentinel has no browser-reachable address (ClusterIP-only), the JS SDK's
 * browser calls route through the app's own origin. Drop this into a catch-all
 * route handler and point the frontend's `sentinelUrl` at its mount path:
 *
 * ```ts
 * // app/api/sentinel/[...path]/route.ts
 * import { createSentinelProxy } from '@sentinel-auth/nextjs/proxy'
 *
 * export const { GET, POST } = createSentinelProxy({
 *   sentinelUrl: process.env.SENTINEL_URL!,        // internal URL
 *   serviceKey: process.env.SENTINEL_SERVICE_KEY!,
 * })
 * ```
 *
 * Frontend config: `sentinelUrl: '/api/sentinel'`,
 * `mintEndpoint: '/api/sentinel/authz/resolve'`.
 *
 * Only the browser-facing surface is forwarded:
 * - `POST authz/resolve` — discovery AND mint; the service key is injected
 *   here (and the caller's tokens dropped), so this route IS the mint endpoint.
 * - `GET workspaces/{id}/members|groups|groups/{id}/members`, `GET users/me` —
 *   the caller's `Authorization` + `X-Authz-Token` pass through untouched and
 *   the service key is deliberately NOT attached: Sentinel ignores
 *   `X-Authz-Token` when a valid service key is present and would reject the
 *   IdP bearer with 401.
 *
 * `X-Forwarded-For` / `User-Agent` pass through so Sentinel's access logs and
 * rate limits see real client IPs (set `BEHIND_PROXY` + `TRUSTED_PROXY_COUNT`
 * on Sentinel).
 */

export interface SentinelProxyConfig {
  /** Internal Sentinel base URL (server-side reachable), e.g. "http://sentinel:9003". */
  sentinelUrl: string
  /** Service API key from the Sentinel admin panel. */
  serviceKey: string
}

type RouteContext = {
  params: { path: string[] } | Promise<{ path: string[] }>
}

type Handler = (req: Request, ctx: RouteContext) => Promise<Response>

const FORWARDED_HEADERS = ['authorization', 'x-authz-token', 'user-agent', 'x-forwarded-for']

/** UUID-shaped path segment — also rules out traversal ("..", encoded slashes). */
const ID = /^[0-9a-fA-F-]{1,64}$/

function matchAllowlist(method: string, path: string[]): boolean {
  const [a, b, c, d, e, ...rest] = path
  if (rest.length > 0) return false
  if (method === 'POST') {
    return a === 'authz' && b === 'resolve' && c === undefined
  }
  if (a === 'users' && b === 'me' && c === undefined) return true
  if (a !== 'workspaces' || !b || !ID.test(b)) return false
  if (c === 'members' && d === undefined) return true
  if (c !== 'groups') return false
  if (d === undefined) return true
  return ID.test(d) && e === 'members'
}

export function createSentinelProxy(config: SentinelProxyConfig): { GET: Handler; POST: Handler } {
  const base = config.sentinelUrl.replace(/\/+$/, '')

  const handler: Handler = async (req, ctx) => {
    const { path } = await ctx.params
    const method = req.method
    if (!matchAllowlist(method, path)) {
      return Response.json({ detail: 'Not found' }, { status: 404 })
    }

    const isMint = method === 'POST'
    const headers = new Headers()
    if (isMint) {
      headers.set('x-service-key', config.serviceKey)
      headers.set('content-type', 'application/json')
      for (const h of ['user-agent', 'x-forwarded-for']) {
        const v = req.headers.get(h)
        if (v) headers.set(h, v)
      }
    } else {
      for (const h of FORWARDED_HEADERS) {
        const v = req.headers.get(h)
        if (v) headers.set(h, v)
      }
    }

    const search = new URL(req.url).search
    let upstream: Response
    try {
      upstream = await fetch(`${base}/${path.join('/')}${search}`, {
        method,
        headers,
        body: isMint ? await req.text() : undefined,
      })
    } catch {
      return Response.json({ detail: 'Sentinel is unreachable' }, { status: 502 })
    }

    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: {
        'content-type': upstream.headers.get('content-type') ?? 'application/json',
      },
    })
  }

  return { GET: handler, POST: handler }
}
