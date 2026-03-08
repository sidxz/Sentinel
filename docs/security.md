# Security

Sentinel is production-hardened with defense-in-depth across transport, authentication, token lifecycle, and input validation. This page documents the full security architecture.

---

## Middleware Stack

Middleware is applied in a specific order. The outermost layer processes requests first:

```
Request
  |
  v
MaxBodySizeMiddleware        -- reject bodies > 10 MB
  |
  v
GlobalRateLimitMiddleware    -- 30 req/min per IP
  |
  v
SecurityHeadersMiddleware    -- security response headers + HSTS
  |
  v
SessionMiddleware            -- encrypted cookie for OAuth2 state
  |
  v
TrustedHostMiddleware        -- Host header validation (production)
  |
  v
DynamicCORSMiddleware        -- cross-origin request policy
  |
  v
Rate Limiting (slowapi)      -- per-endpoint throttling
  |
  v
Application Routes
```

Source: `service/src/main.py`

---

## Security Headers

Every response includes 11 security headers set by `SecurityHeadersMiddleware`:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevents MIME type sniffing |
| `X-Frame-Options` | `DENY` | Blocks clickjacking via iframes |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limits referrer leakage |
| `X-XSS-Protection` | `0` | Disables legacy XSS filter (CSP preferred) |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Restricts browser APIs |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` | Blocks all resource loading and framing |
| `Cross-Origin-Embedder-Policy` | `require-corp` | Prevents cross-origin resource leaks |
| `Cross-Origin-Opener-Policy` | `same-origin` | Isolates browsing context |
| `Cross-Origin-Resource-Policy` | `same-origin` | Restricts resource sharing |
| `X-Permitted-Cross-Domain-Policies` | `none` | Blocks Flash/PDF cross-domain access |
| `Server` | `daikon` | Masks underlying server technology |

Sensitive paths (`/auth`, `/admin`, `/users`) additionally receive `Cache-Control: no-store` and `Pragma: no-cache`.

When `COOKIE_SECURE=true`, HSTS is enabled:

```
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
```

This enforces HTTPS for two years and is eligible for the [HSTS preload list](https://hstspreload.org/).

Source: `service/src/middleware/security_headers.py`

---

## Authentication Tiers

Four tiers, applied by endpoint sensitivity:

| Tier | Mechanism | Use Case | Example Endpoints |
|------|-----------|----------|-------------------|
| **User JWT** | `Authorization: Bearer <token>` | End-user actions | `/users/me`, `/workspaces`, `/groups` |
| **Service Key + JWT** | `X-Service-Key` + `Authorization: Bearer` | Service acting on behalf of a user | `/permissions/check`, `/permissions/accessible` |
| **Service Key Only** | `X-Service-Key` header | Autonomous service operations | `/permissions/register`, `/permissions/visibility` |
| **Admin Cookie** | `admin_token` HttpOnly cookie | Admin panel operations | `/admin/*` |

Service keys are database-managed (`service_apps` table), not environment variables. Each key is stored as a SHA-256 hash with a display prefix (e.g., `sk_abc1****`). Keys are validated by `service_app_service.validate_key()` with Redis caching.

---

## JWT Security

### RS256 Signing

All tokens use RS256 (RSA + SHA-256). The private key signs tokens; any service with the public key can verify without contacting Sentinel.

```bash
openssl genrsa -out keys/private.pem 2048
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
```

The public key is also available at `/.well-known/jwks.json`.

### Audience Separation

Tokens carry a `type` claim that prevents cross-use:

| Token Type | `type` Claim | Audience |
|------------|-------------|----------|
| Access token | `access` | `sentinel:access` |
| Refresh token | (Redis only) | N/A |
| Admin token | `admin_access` | `sentinel:admin` |
| Authz token | `authz_access` | `sentinel:authz` |

### Token ID (`jti`)

Every token includes a `jti` (UUID). This enables per-token revocation via the Redis denylist without invalidating all tokens for a user.

### Access Token Claims

| Claim | Type | Description |
|-------|------|-------------|
| `sub` | UUID | User ID |
| `jti` | UUID | Token identifier (for revocation) |
| `email` | string | User email |
| `name` | string | Display name |
| `wid` | UUID | Workspace ID |
| `wslug` | string | Workspace slug |
| `wrole` | string | Workspace role (`owner`/`admin`/`editor`/`viewer`) |
| `groups` | UUID[] | Group IDs in this workspace |
| `type` | string | `"access"` |
| `iat` / `exp` | timestamp | Issued at / expiration |

### Token Lifetimes

| Token | Default | Config Variable |
|-------|---------|-----------------|
| Access | 15 minutes | `ACCESS_TOKEN_EXPIRE_MINUTES` |
| Refresh | 7 days | `REFRESH_TOKEN_EXPIRE_DAYS` |
| Admin | 1 hour | `ADMIN_TOKEN_EXPIRE_MINUTES` |
| Authz | 5 minutes | `AUTHZ_TOKEN_EXPIRE_MINUTES` |

---

## Token Lifecycle

### Refresh Token Rotation

Modeled after [Auth0's refresh rotation](https://auth0.com/docs/secure/tokens/refresh-tokens/refresh-token-rotation):

1. **Issuance** -- on authentication, the service issues an access + refresh token pair. The refresh token's `jti` is stored in Redis with a `family_id`.
2. **Rotation** -- `POST /auth/refresh` atomically consumes the token (`GETDEL`), issues a new pair in the same family.
3. **Reuse detection** -- a consumed token presented again signals theft. The entire family is revoked.
4. **Family revocation** -- on theft detection or user deactivation, all `jti` entries in the family set are deleted.

Redis keys:

| Key | Value | TTL |
|-----|-------|-----|
| `rt:{jti}` | `{user_id}:{family_id}` | `REFRESH_TOKEN_EXPIRE_DAYS` |
| `rtf:{family_id}` | Set of `jti` values | `REFRESH_TOKEN_EXPIRE_DAYS` |

### Authorization Codes

After OAuth callback, Sentinel issues a short-lived authorization code (not raw user IDs in redirects):

1. Frontend sends `code_challenge` + `code_challenge_method=S256` on `GET /auth/login/{provider}`
2. Callback stores the code in Redis with a 5-minute TTL alongside the `code_challenge`
3. `GET /auth/workspaces?code=X` peeks at the code (non-destructive)
4. `POST /auth/token` verifies `SHA256(code_verifier) == code_challenge`, then consumes the code via `GETDEL`

Redis key: `ac:{code}` -- JSON `{user_id, provider, code_challenge, code_challenge_method}`, 5-minute TTL.

### Access Token Revocation

On logout, the `jti` is added to a Redis denylist with TTL equal to the token's remaining lifetime. Every authenticated request checks the denylist. Entries self-expire when the token would have expired anyway.

Redis key: `bl:{jti}` -- value `"1"`, TTL = remaining seconds.

### Logout Completeness

`POST /auth/logout` performs two actions:

1. Blacklists the access token (`jti` to denylist)
2. Revokes all refresh token families for the user (`revoke_all_user_tokens`)

This prevents an attacker with a captured refresh token from obtaining new access tokens after the user logs out.

---

## Cookie Security

Admin cookies are configured for defense in depth:

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `httponly` | `True` | Prevents JavaScript access (XSS mitigation) |
| `samesite` | `strict` | Blocks cross-site request inclusion |
| `secure` | `COOKIE_SECURE` | Restricts to HTTPS when enabled |
| `max_age` | `3600` | Expires after 1 hour |
| `path` | `/` | Available across all routes |

### CSRF Protection

Two layers:

1. **SameSite=Strict** -- the `admin_token` cookie is never sent on cross-site requests.
2. **Custom header** -- all mutation requests (POST/PATCH/PUT/DELETE) to `/admin/*` require `X-Requested-With: XMLHttpRequest`. This header cannot be set by cross-origin forms, and CORS preflight blocks cross-origin JavaScript from adding it.

### Session Cookies

`SessionMiddleware` provides encrypted session cookies used exclusively during OAuth2 flows. The session stores `state` and PKCE `code_verifier` between redirect and callback. Sessions expire after 10 minutes (`max_age=600`).

```bash
# Generate a session secret (required for production)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Rate Limiting

Two layers:

1. **Global** -- `GlobalRateLimitMiddleware` enforces 30 requests/minute per IP across all endpoints (except `/health`). Uses a Redis-backed atomic counter (Lua INCR+EXPIRE).
2. **Per-endpoint** -- slowapi applies stricter limits on sensitive endpoints.

| Endpoint | Limit | Rationale |
|----------|-------|-----------|
| All endpoints | 30/min (global) | Baseline abuse prevention |
| `GET /auth/login/{provider}` | 10/min | Prevents OAuth redirect abuse |
| `GET /auth/callback/{provider}` | 10/min | Limits callback processing |
| `POST /auth/token` | 10/min | Prevents auth code brute-force |
| `POST /auth/refresh` | 10/min | Prevents refresh token brute-force |
| `GET /auth/admin/login/{provider}` | 5/min | Stricter limit on admin login |
| `GET /auth/admin/callback/{provider}` | 5/min | Stricter limit on admin callback |

When `BEHIND_PROXY=true`, the rate limiter reads client IP from `X-Forwarded-For` instead of the TCP connection address.

Exceeding either limit returns `429 Too Many Requests` with a `Retry-After` header.

---

## OAuth Hardening

### PKCE (S256)

PKCE prevents authorization code interception. Sentinel uses S256 where supported:

| Provider | PKCE | Notes |
|----------|------|-------|
| Google | S256 | Full OIDC |
| Microsoft Entra ID | S256 | Full OIDC |
| GitHub | No | Does not support PKCE; relies on `state` |

PKCE is configured at the Authlib client registration level. Authlib generates `code_verifier` and `code_challenge` automatically.

### Client App Allowlist

Applications must be registered as client apps before using Sentinel. Each app defines allowed redirect URIs. Sentinel validates that `redirect_uri` on `GET /auth/login/{provider}` belongs to an active registered app.

This prevents unauthorized usage and open redirector attacks.

### State Parameter

All OAuth2 flows use `state` (managed by Authlib via `SessionMiddleware`) to prevent CSRF during authorization code exchange.

### CORS

`DynamicCORSMiddleware` combines two origin sources:

1. **Static** -- from `CORS_ORIGINS` environment variable
2. **Dynamic** -- derived from `client_apps.redirect_uris` in the database

Policy: credentials enabled, methods `GET/POST/PUT/PATCH/DELETE/OPTIONS`, headers `Content-Type`, `Authorization`, `X-Service-Key`. No wildcards in production.

---

## Input Validation

### Pydantic Schemas

All request bodies are validated with Pydantic models. Invalid input is rejected with `422` before reaching business logic. This covers type checking, UUID format validation, enum constraints, and required/optional field enforcement.

### Request Body Size

`MaxBodySizeMiddleware` rejects requests exceeding 10 MB (`413 Request Entity Too Large`). It checks both `Content-Length` headers and actual streamed bytes to catch chunked uploads. CSV import endpoints enforce a stricter 5 MB limit at the application level.

### Action Name Validation

RBAC action names must match `^[a-z][a-z0-9_.:-]*$`, namespaced by `service_name`.

---

## Startup Checks (Fail-Closed)

When `DEBUG=false`, the service refuses to start if any check fails:

| Check | Failure Condition | Error |
|-------|-------------------|-------|
| Session secret | Default value unchanged | `SESSION_SECRET_KEY is using the default dev value` |
| Service apps | No active apps in DB | `No active service apps registered` |
| Cookie security | `COOKIE_SECURE=false` | `COOKIE_SECURE is False` |
| Redis connectivity | Cannot ping | `Redis is unreachable` |
| Redis auth | No `@` in `REDIS_URL` | `Redis URL has no authentication` |
| Allowed hosts | Resolved to `*` | `ALLOWED_HOSTS is wildcard` |

Redis TLS and certificate verification are checked separately and logged as warnings (not blocking).

In development (`DEBUG=true`), all checks are logged as warnings instead.

---

## Trusted Host Validation

When `ALLOWED_HOSTS` resolves to anything other than `*`, `TrustedHostMiddleware` validates the `Host` header on every request. This prevents Host header injection attacks used in cache poisoning.

If `ALLOWED_HOSTS` is empty, hostnames are derived from `BASE_URL` and `ADMIN_URL`.

---

## SDK Insecure URL Warnings

All SDK clients (Python and JavaScript) log a warning when initialized with a plain `http://` URL not pointing to localhost. This catches accidental production deployments without HTTPS.

| SDK | Warning |
|-----|---------|
| Python (`sentinel-auth-sdk`) | `logging.warning()` via `sentinel_auth` logger |
| JS (`@sentinel-auth/js`) | `console.warn()` |
| Next.js (`@sentinel-auth/nextjs`) | `console.warn()` in `createSentinelMiddleware` |

---

## Production Checklist

- [ ] `SESSION_SECRET_KEY` set to a cryptographically random value
- [ ] `COOKIE_SECURE=true` and service is behind TLS
- [ ] `DEBUG=false`
- [ ] `BEHIND_PROXY=true` if behind a reverse proxy
- [ ] `ALLOWED_HOSTS` set to actual domain(s)
- [ ] `CORS_ORIGINS` lists only your frontend origin(s)
- [ ] RS256 key pair generated, private key `chmod 600`
- [ ] At least one service app registered via admin panel
- [ ] PostgreSQL uses SSL (`?ssl=require` in `DATABASE_URL`)
- [ ] Redis uses TLS (`rediss://`), has a strong password, not publicly exposed
- [ ] `REDIS_TLS_VERIFY=required` with CA cert configured
- [ ] `ADMIN_EMAILS` set for auto-promotion
- [ ] TLS certs generated for Postgres and Redis (`keys/tls/`)
- [ ] Reverse proxy handles TLS termination and sets `X-Forwarded-For`
- [ ] Startup validation passes with `DEBUG=false`
