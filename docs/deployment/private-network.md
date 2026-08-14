# Private-Network Deployment

Sentinel does not need a public address. In authz mode, user login happens at
the IdP (Google/EntraID), token minting already routes through your backend,
and the SDKs ship reverse-proxy helpers for the remaining browser-facing reads
— so Sentinel can live on a cluster-internal network reachable only by your app
backends.

```
Browser ──▶ IdP (Google/EntraID) ──▶ back to app origin with id_token
Browser ──▶ App backend /api/sentinel/* ──▶ Sentinel (internal)   ← proxy helpers
App backend ──▶ Sentinel (permissions, roles, m2m, JWKS)          ← already internal
```

## Sentinel service

- **Kubernetes**: ClusterIP Service, no Ingress. Add a NetworkPolicy allowing
  ingress only from app-backend pods. **Docker Swarm**: attach Sentinel to an
  internal overlay network; publish no ports.
- Run a single listener with `TIER=all`. The public/internal tier split guards
  a public socket; with nothing published, the network boundary does that job.
- Set `BASE_URL` to the internal DNS name (e.g. `http://sentinel.auth.svc:9003`).
  `BASE_URL` is the JWT `iss` claim — app-side verifiers must use the same value.
- Sentinel still needs **outbound** HTTPS to the IdPs (JWKS, token exchange).

## App backends: mount the proxy

Each app forwards exactly the browser-facing surface — discovery/mint via
`POST /authz/resolve` (service key injected server-side) plus the read-only
directory endpoints (members, groups, group members, `/users/me`) with the
caller's tokens passed through. Nothing else is reachable.

FastAPI (Python SDK):

```python
app.include_router(sentinel.proxy_router(), prefix="/api/sentinel")
```

Next.js — `app/api/sentinel/[...path]/route.ts`:

```ts
import { createSentinelProxy } from '@sentinel-auth/nextjs/proxy'

export const { GET, POST } = createSentinelProxy({
  sentinelUrl: process.env.SENTINEL_URL!,        // internal URL
  serviceKey: process.env.SENTINEL_SERVICE_KEY!,
})
```

## Frontends

```ts
const authz = new SentinelAuthz({
  sentinelUrl: '/api/sentinel',                    // same-origin proxy mount
  mintEndpoint: '/api/sentinel/authz/resolve',     // the proxy IS the mint endpoint
  // ...idps, storage as usual
})
```

The Next.js Edge middleware keeps the **internal** URL — it verifies tokens
server-side and derives JWKS/issuer from it:

```ts
createSentinelAuthzMiddleware({ sentinelUrl: process.env.SENTINEL_URL!, ... })
```

## Preserving client IPs in logs and rate limits

The proxy helpers forward `X-Forwarded-For` and `User-Agent` unchanged. For
Sentinel's access logs, security events, and per-IP rate limits to see real
client IPs, set on Sentinel:

```env
BEHIND_PROXY=true
TRUSTED_PROXY_COUNT=1   # proxies that APPEND to XFF — typically just your ingress
```

The app-backend hop passes XFF through without appending, so it does not count.

## Caveats

- **GitHub as IdP is unsupported** in this topology — its proxy-login flow
  needs a browser-reachable Sentinel. Google/EntraID implicit flows are
  unaffected: the browser talks to the IdP and returns to **your app's** origin,
  so the IdP never needs a route to Sentinel. Only Sentinel's outbound JWKS
  fetch does — allow egress to `login.microsoftonline.com` (Entra) or
  `www.googleapis.com` (Google) in your NetworkPolicy / Azure Firewall.
- **Admin panel** is internal-only (a feature): reach it via VPN, jumpbox, or
  `kubectl port-forward`. Note that admin OAuth builds its redirect URI as
  `{BASE_URL}/auth/admin/callback/{provider}` — with `BASE_URL` set to internal
  DNS, the IdP bounces the browser to a host it cannot resolve. Either make the
  admin's local address answer at exactly that host and port (hosts-file entry +
  `kubectl port-forward`, and register that URI with the IdP), or give the admin
  surface its own restricted ingress.
- **`/authz/resolve` rate limit** is keyed by service key, so one app's entire
  login+refresh volume shares a bucket — size `RATE_LIMIT_AUTHZ_RESOLVE`
  accordingly.
