---
title: Security
description: Security architecture, authentication tiers, and hardening measures for the Sentinel Auth
---

# Security

This document describes the security architecture of the Sentinel Auth, covering transport security, authentication mechanisms, token lifecycle, service-to-service auth, and input validation.

---

## Middleware Stack

The service applies middleware in a specific order (outermost first):

```
Request
  |
  v
MaxBodySizeMiddleware        -- reject requests > 10 MB
  |
  v
GlobalRateLimitMiddleware    -- 30 req/min per IP (all endpoints)
  |
  v
SecurityHeadersMiddleware    -- security response headers
  |
  v
SessionMiddleware            -- encrypted session for OAuth2 state
  |
  v
TrustedHostMiddleware        -- Host header validation (production)
  |
  v
CORSMiddleware               -- cross-origin request policy
  |
  v
Rate Limiting (slowapi)      -- per-endpoint request throttling
  |
  v
Application Routes
```

### Security Headers

Every response includes the following headers, set by `SecurityHeadersMiddleware`:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevents MIME type sniffing |
| `X-Frame-Options` | `DENY` | Blocks clickjacking via iframes |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limits referrer leakage |
| `X-XSS-Protection` | `0` | Disables legacy XSS filter (modern CSP preferred) |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Restricts browser APIs |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` | Blocks all resource loading and framing |
| `Cross-Origin-Embedder-Policy` | `require-corp` | Prevents cross-origin resource leaks |
| `Cross-Origin-Opener-Policy` | `same-origin` | Isolates browsing context |
| `Cross-Origin-Resource-Policy` | `same-origin` | Restricts resource sharing to same origin |
| `X-Permitted-Cross-Domain-Policies` | `none` | Blocks Flash/PDF cross-domain access |
| `Server` | `daikon` | Masks underlying server technology |

#### HSTS

When `COOKIE_SECURE=true` (production with HTTPS), the service adds:

```
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
```

This enforces HTTPS for two years, covers all subdomains, and is eligible for the [HSTS preload list](https://hstspreload.org/). Only enable this when your deployment is fully behind TLS.

### Session Middleware

Starlette's `SessionMiddleware` provides encrypted, signed cookies used exclusively by Authlib during the OAuth2 authorization code flow. The session stores the `state` parameter and PKCE `code_verifier` between the redirect and callback steps.

**Configuration:**

```bash
# Generate a strong secret (required in production)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

```env
SESSION_SECRET_KEY=your-generated-secret-here
```

The default value `dev-only-change-me-in-production` is intentionally weak and must be replaced before deployment.

### Trusted Host Middleware

When `ALLOWED_HOSTS` is set to anything other than `*`, Starlette's `TrustedHostMiddleware` validates the `Host` header on every request. This prevents Host header injection attacks used in cache poisoning and password reset exploits.

```env
# Development (disabled)
ALLOWED_HOSTS=*

# Production
ALLOWED_HOSTS=identity.example.com,api.example.com
```

### CORS

Cross-Origin Resource Sharing is handled by `DynamicCORSMiddleware`, which combines static and database-backed origins:

1. **Static origins** from the `CORS_ORIGINS` environment variable
2. **Dynamic origins** extracted from `client_apps.redirect_uris` in the database — the middleware derives the origin (`scheme://host[:port]`) from each registered redirect URI

Origins are refreshed from the database on startup.

```env
CORS_ORIGINS=https://app.example.com,https://admin.example.com
```

The CORS policy allows:

- **Origins**: Static origins from `CORS_ORIGINS` + origins derived from registered client app redirect URIs (no wildcards in production)
- **Credentials**: Enabled (`allow_credentials=True`) for cookie-based admin auth
- **Methods**: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`
- **Headers**: `Content-Type`, `Authorization`, `X-Service-Key`

---

## Authentication

### Auth Tiers

The service uses four authentication tiers, applied depending on the sensitivity and audience of each endpoint:

| Tier | Mechanism | Use Case | Example Endpoints |
|------|-----------|----------|-------------------|
| **User JWT** | `Authorization: Bearer <token>` | End-user actions scoped to a workspace | `/users/me`, `/workspaces`, `/groups` |
| **Service Key + User JWT** | `X-Service-Key` header + `Authorization: Bearer` | Service acting on behalf of a user | `/permissions/check`, `/permissions/accessible`, `POST /permissions/{id}/share` |
| **Service Key Only** | `X-Service-Key` header | Autonomous service operations | `/permissions/register`, `/permissions/visibility`, `DELETE /permissions/{id}/share` |
| **Admin Cookie** | `admin_token` HttpOnly cookie | Admin panel operations | `/auth/admin/me`, `/admin/*` |

### RS256 JWT Tokens

All tokens are signed with RS256 (RSA + SHA-256) using a private key and verified with the corresponding public key. This allows any service with the public key to validate tokens without contacting the identity service.

**Key generation:**

```bash
openssl genrsa -out keys/private.pem 2048
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
```

**Access token claims:**

| Claim | Type | Description |
|-------|------|-------------|
| `sub` | UUID | User ID |
| `jti` | UUID | Unique token identifier (for revocation) |
| `email` | string | User email |
| `name` | string | User display name |
| `wid` | UUID | Workspace ID |
| `wslug` | string | Workspace slug |
| `wrole` | string | Workspace role (`owner`, `admin`, `editor`, `viewer`) |
| `groups` | UUID[] | Group IDs the user belongs to in this workspace |
| `type` | string | `"access"` |
| `iat` | timestamp | Issued at |
| `exp` | timestamp | Expiration (default: 15 minutes) |

**Admin token claims:**

| Claim | Type | Description |
|-------|------|-------------|
| `sub` | UUID | User ID |
| `jti` | UUID | Unique token identifier (for revocation) |
| `email` | string | User email |
| `name` | string | User display name |
| `admin` | boolean | Always `true` |
| `type` | string | `"admin_access"` |
| `iat` | timestamp | Issued at |
| `exp` | timestamp | Expiration (default: 1 hour) |

**Token lifetimes:**

| Token | Default Lifetime | Configurable Via |
|-------|-----------------|------------------|
| Access token | 15 minutes | `ACCESS_TOKEN_EXPIRE_MINUTES` |
| Refresh token | 7 days | `REFRESH_TOKEN_EXPIRE_DAYS` |
| Admin token | 1 hour | `ADMIN_TOKEN_EXPIRE_MINUTES` |

---

## Token Lifecycle

### Refresh Token Rotation

The service implements refresh token rotation with **reuse detection**, modeled after the approach described in [Auth0's documentation](https://auth0.com/docs/secure/tokens/refresh-tokens/refresh-token-rotation):

1. **Issuance**: When a user authenticates, the service issues an access token and a refresh token. The refresh token's `jti` is stored in Redis along with a `family_id`.

2. **Rotation**: When the client presents a refresh token at `POST /auth/refresh`, the service:
    - Atomically consumes the token (`GETDEL` in Redis -- one-time use)
    - Issues a new access + refresh token pair
    - Stores the new refresh token in the **same family**

3. **Reuse detection**: If a consumed refresh token is presented again, the service rejects it. This signals potential token theft -- an attacker replaying a stolen token after the legitimate client already rotated it.

4. **Family revocation**: When theft is detected or a user is deactivated, the service revokes the entire token family by deleting all `jti` entries in the family set.

**Redis key structure:**

| Key Pattern | Value | TTL |
|-------------|-------|-----|
| `rt:{jti}` | `{user_id}:{family_id}` | `REFRESH_TOKEN_EXPIRE_DAYS` |
| `rtf:{family_id}` | Set of `jti` values | `REFRESH_TOKEN_EXPIRE_DAYS` |

### Authorization Codes

After a successful OAuth callback, the service issues a short-lived authorization code instead of passing the raw `user_id` in the redirect URL. This prevents token theft by anyone who knows a user's UUID.

**PKCE is mandatory** on Sentinel's own auth codes (S256 only). The frontend must generate a `code_verifier` and `code_challenge` before initiating login, pass the `code_challenge` on `GET /auth/login/{provider}`, and include the `code_verifier` when exchanging the code at `POST /auth/token`. This binds the auth code exchange to the original initiator, preventing authorization code interception attacks.

1. The frontend sends `code_challenge` and `code_challenge_method=S256` as query params on the login endpoint
2. The callback generates a cryptographically random code and stores it in Redis with a 5-minute TTL (alongside the `code_challenge`)
3. The client uses the code to fetch workspaces (`GET /auth/workspaces?code=X`) — this **peeks** at the code without consuming it
4. The client exchanges the code for tokens (`POST /auth/token` with `{code, workspace_id, code_verifier}`) — Sentinel verifies `SHA256(code_verifier) == code_challenge`, then **consumes** the code atomically via `GETDEL`
5. A consumed code cannot be reused; a second exchange attempt returns `400`

**Redis key structure:**

| Key Pattern | Value | TTL |
|-------------|-------|-----|
| `ac:{code}` | JSON `{user_id, provider, code_challenge, code_challenge_method}` | 5 minutes |

### Access Token Revocation

Access tokens can be revoked before expiration (e.g., on logout) using a Redis denylist:

1. Client calls `POST /auth/logout` with the access token in the `Authorization` header
2. The service extracts the `jti` and `exp` from the token
3. The `jti` is added to the denylist with a TTL equal to the token's remaining lifetime
4. On every authenticated request, the `get_current_user` dependency checks the denylist

**Redis key structure:**

| Key Pattern | Value | TTL |
|-------------|-------|-----|
| `bl:{jti}` | `"1"` | Remaining seconds until token expiration |

This approach keeps the denylist small -- entries automatically expire when the token would have expired anyway.

### Admin Token Revocation

Admin tokens follow the same denylist pattern as access tokens. When an admin logs out via `POST /auth/admin/logout`:

1. The endpoint requires a valid admin cookie (`Depends(require_admin)`)
2. The `jti` from the admin token is added to the Redis denylist
3. The `admin_token` cookie is deleted from the response
4. On subsequent requests, `require_admin` checks the denylist before granting access

### Logout Completeness

User logout (`POST /auth/logout`) performs two actions:

1. **Blacklists the access token** — adds `jti` to the Redis denylist
2. **Revokes all refresh token families** — calls `revoke_all_user_tokens(user_id)` to invalidate every refresh token the user has, preventing an attacker with a captured refresh token from obtaining new access tokens after the user logs out

---

## Service-to-Service Authentication

Backend services authenticate to the identity service using the `X-Service-Key` header. This is used for permission and role operations where a service acts autonomously or on behalf of a user.

### Service Apps (Database-Managed Keys)

Service API keys are managed through the **service apps** system in the admin panel (`/admin/service-apps`), not environment variables. Each service app has:

- **`name`** — human-readable label
- **`service_name`** — the service this key is scoped to (verified by `verify_service_scope()`)
- **`key_hash`** — SHA-256 hash of the plaintext key (the plaintext is shown once at creation)
- **`key_prefix`** — first few characters for identification (e.g., `sk_abc1****`)
- **`is_active`** — can be deactivated without deletion

Keys are validated by `service_app_service.validate_key()`, which checks the SHA-256 hash against active service apps (with Redis caching).

### Behavior

| Service Apps in DB | Request Without Key | Request With Invalid Key | Request With Valid Key |
|--------------------|--------------------|--------------------------|-----------------------|
| None active (dev mode) | Allowed | Allowed | Allowed |
| At least one active (production) | 401 Unauthorized | 401 Unauthorized | Allowed |

**Dev mode** is intentionally permissive: when no active service apps exist in the database, the `require_service_key` dependency passes through all requests. This allows local development without configuring keys. In production, register at least one service app via the admin panel.

### Dual Auth (Service Key + User JWT)

Some endpoints require both a service key and a user JWT. This pattern is used when a service needs to perform an action on behalf of a specific user -- the service key authenticates the calling service, and the JWT identifies the user:

```
POST /permissions/check
X-Service-Key: sk_prod_abc123
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
```

---

## Cookie Security

The admin panel uses HttpOnly cookies for session management. Cookie attributes are configured for defense in depth:

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `httponly` | `True` | Prevents JavaScript access (XSS mitigation) |
| `samesite` | `strict` | Blocks cross-site request inclusion (CSRF mitigation) |
| `secure` | `COOKIE_SECURE` setting | Restricts to HTTPS when enabled |
| `max_age` | `3600` (1 hour) | Cookie expires after 1 hour |
| `path` | `/` | Available across all routes |

```env
# Development (HTTP)
COOKIE_SECURE=false

# Production (HTTPS)
COOKIE_SECURE=true
```

When `COOKIE_SECURE=true`, the `Secure` flag ensures the cookie is only sent over HTTPS connections. Additionally, this flag enables HSTS headers on all responses.

### CSRF Protection

The admin panel uses two layers of CSRF defense:

1. **SameSite=Strict cookie** -- the `admin_token` cookie is never sent on cross-site requests
2. **Custom header requirement** -- all state-changing requests (POST, PATCH, PUT, DELETE) to `/admin/*` must include an `X-Requested-With` header. This header cannot be set by cross-origin HTML forms or image tags, and CORS preflight blocks cross-origin JavaScript from adding it.

The admin SPA automatically includes `X-Requested-With: XMLHttpRequest` on all requests. Requests without this header on mutation endpoints receive a `403 Forbidden`.

---

## Rate Limiting

Rate limiting uses two layers:

1. **Global rate limit** — `GlobalRateLimitMiddleware` enforces **30 requests/minute per IP** across all endpoints (except `/health`). This is a simple in-memory sliding window that catches broad abuse regardless of endpoint.

2. **Per-endpoint limits** — [slowapi](https://github.com/laurentS/slowapi) applies stricter limits on sensitive endpoints. These fire before the global limit.

When a client exceeds either limit, the service responds with `429 Too Many Requests` and a `Retry-After` header.

### Endpoint Limits

| Endpoint | Limit | Rationale |
|----------|-------|-----------|
| All endpoints | 30/minute (global) | Baseline abuse prevention |
| `GET /auth/login/{provider}` | 10/minute | Prevents OAuth redirect abuse |
| `GET /auth/callback/{provider}` | 10/minute | Limits callback processing |
| `GET /auth/workspaces` | 10/minute | Limits workspace listing during auth |
| `POST /auth/token` | 10/minute | Prevents auth code brute-force |
| `POST /auth/refresh` | 10/minute | Prevents refresh token brute-force |
| `GET /auth/admin/login/{provider}` | 5/minute | Stricter limit on admin login |
| `GET /auth/admin/callback/{provider}` | 5/minute | Stricter limit on admin callback |

Rate limit state is keyed by the client's remote IP address. If the service is behind a reverse proxy, ensure `X-Forwarded-For` is configured correctly so the real client IP is used.

---

## OAuth Hardening

### PKCE (Proof Key for Code Exchange)

PKCE prevents authorization code interception attacks. The service uses **S256** (SHA-256) code challenge method on providers that support it:

| Provider | PKCE | Method | Notes |
|----------|------|--------|-------|
| Google | Yes | S256 | Full OIDC with `openid email profile` scope |
| Microsoft EntraID | Yes | S256 | Full OIDC with `openid email profile` scope |
| GitHub | No | N/A | GitHub does not support PKCE as of 2025; relies on `state` parameter |

PKCE is configured at the Authlib client registration level via `code_challenge_method="S256"`. Authlib automatically generates the `code_verifier` and `code_challenge`, storing the verifier in the session for validation during the callback.

### Client App Allowlist

Applications must be registered as **client apps** before they can use Sentinel. Each client app defines a set of allowed redirect URIs. Sentinel proxies authentication from external IdPs and validates that the `redirect_uri` belongs to an active registered app.

- `GET /auth/login/{provider}` requires a `redirect_uri` that is registered on an active client app
- Only pre-approved redirect URIs can receive authorization codes

This prevents:

- **Unauthorized usage** — unregistered applications cannot initiate login flows or obtain tokens
- **Open redirector attacks** — the callback can only redirect to pre-approved URIs

Client apps can be deactivated without deletion to temporarily block an application.

### State Parameter

All OAuth2 flows use the `state` parameter (managed by Authlib via `SessionMiddleware`) to prevent CSRF attacks during the authorization code exchange. The state is generated on redirect, stored in the encrypted session cookie, and validated on callback.

---

## Input Validation

### Pydantic Schemas

All request bodies are validated with Pydantic models. Invalid input is rejected with a `422 Unprocessable Entity` response before reaching any business logic. This includes:

- Type checking and coercion
- UUID format validation
- Enum value constraints (e.g., workspace roles, permission actions)
- Required vs. optional field enforcement

### Request Body Size Limit

A global `MaxBodySizeMiddleware` rejects any request with a `Content-Length` exceeding **10 MB**, returning `413 Request Entity Too Large`. This prevents memory exhaustion from oversized payloads.

Additionally, CSV import endpoints (admin panel) enforce a stricter **5 MB file size limit** at the application level.

---

## Configuration Reference

All security-related environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_SECRET_KEY` | `dev-only-change-me-in-production` | Secret for signing session cookies (OAuth2 state) |
| `COOKIE_SECURE` | `false` | Set `true` in production to enable `Secure` flag and HSTS |
| `ALLOWED_HOSTS` | `""` (empty) | Derived from `BASE_URL` + `ADMIN_URL` hostnames. Falls back to `["*"]` only if no hostnames found. |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:9101` | Comma-separated static CORS origins (combined with DB client app origins at runtime) |
| `JWT_PRIVATE_KEY_PATH` | `keys/private.pem` | Path to RS256 private key for signing tokens |
| `JWT_PUBLIC_KEY_PATH` | `keys/public.pem` | Path to RS256 public key for verifying tokens |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime in minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime in days |
| `ADMIN_TOKEN_EXPIRE_MINUTES` | `60` | Admin token lifetime in minutes |
| `DEBUG` | `true` | Set `false` in production to disable `/docs`, `/redoc`, `/openapi.json` |
| `ADMIN_EMAILS` | (empty) | Comma-separated emails auto-promoted to admin on login |
| `REDIS_URL` | `redis://localhost:9002/0` | Redis connection string. Use `rediss://` for TLS and include password: `rediss://:password@host:6379/0` |

---

## Startup Validation

When `DEBUG=false`, the service performs fail-closed validation at startup and **refuses to start** if any check fails:

| Check | Condition | Error |
|-------|-----------|-------|
| Session secret | Default value unchanged | `SESSION_SECRET_KEY is using the default dev value` |
| Service apps | No active service apps in DB | `No active service apps registered` |
| Cookie security | `COOKIE_SECURE=false` | `COOKIE_SECURE is False` |
| Redis connectivity | Cannot ping Redis | `Redis is unreachable` |
| Redis authentication | No `@` in `REDIS_URL` | `Redis URL has no authentication` |
| Redis TLS | URL does not start with `rediss://` | `Redis URL is not using TLS` |
| Allowed hosts | Resolved to wildcard `*` | `ALLOWED_HOSTS is wildcard` |

In development (`DEBUG=true`), these are logged as warnings instead of blocking startup.

---

## Penetration Testing

The `pentest/` directory contains a comprehensive security testing suite combining industry-standard tools with custom scripts.

### Running

```bash
# Install tools (one-time)
make pentest-setup

# Run everything
make pentest

# Custom scripts only (no external tools)
make pentest-custom

# Single tool
cd pentest && python run_all.py --nuclei
```

### External Tools

| Tool | What It Tests |
|------|---------------|
| **OWASP ZAP** | API scanning via OpenAPI spec — injection, auth bypass, misconfigurations |
| **Nuclei** | Template-based vulnerability and misconfiguration detection |
| **Nikto** | Web server misconfiguration, default files, header issues |
| **jwt_tool** | JWT-specific attacks — algorithm confusion, `none` bypass, claim injection |

### Custom Scripts

Ten test suites covering ~110 individual tests:

| Suite | Coverage |
|-------|----------|
| JWT Attacks | Algorithm confusion, token forgery, claim tampering, JWK/KID injection |
| Admin Bypass | Cookie theft/replay, privilege escalation, token revocation |
| IDOR & AuthZ | Cross-workspace access, resource ID enumeration, role bypass |
| Service Key | Dev-mode bypass, key brute-force, missing enforcement |
| Rate Limiting | Header spoofing, endpoint flooding, evasion techniques |
| Injection & XSS | SQL injection, stored XSS, CSV injection, path traversal |
| Session & OAuth | Session fixation, state tampering, CSRF, redirect manipulation |
| Info Disclosure | OpenAPI exposure, error verbosity, header leakage |
| Token Lifecycle | Refresh rotation abuse, reuse detection, logout bypass |
| Attack Chains | End-to-end scenarios chaining multiple vulnerabilities |

### Reports

All output is saved to `pentest/reports/`:

- `summary.json` — combined results from all tools and custom scripts
- `zap_report.json`, `nuclei_findings.jsonl`, `nikto_report.json`, `jwt_tool_results.txt`

---

## Production Checklist

Before deploying to production, verify the following:

- [ ] `SESSION_SECRET_KEY` is set to a cryptographically random value (not the default)
- [ ] At least one service app is registered via the admin panel (`/admin/service-apps`) with a strong key
- [ ] `COOKIE_SECURE=true` and the service is behind TLS
- [ ] `ALLOWED_HOSTS` is set to your actual domain(s), not `*`
- [ ] `CORS_ORIGINS` lists only your frontend origin(s)
- [ ] RS256 key pair is generated and `JWT_PRIVATE_KEY_PATH` / `JWT_PUBLIC_KEY_PATH` point to the correct files
- [ ] The private key file has restrictive permissions (`chmod 600`)
- [ ] `DEBUG=false` to disable OpenAPI docs (`/docs`, `/redoc`, `/openapi.json`)
- [ ] `ADMIN_EMAILS` is set if you want auto-promotion for specific users
- [ ] A reverse proxy (nginx, Caddy, or cloud LB) handles TLS termination and sets `X-Forwarded-For`
- [ ] Redis uses TLS (`rediss://`), has a strong password, and is not exposed to the public internet
- [ ] PostgreSQL uses strong credentials and is not exposed to the public internet
- [ ] Startup validation passes with `DEBUG=false` (all checks green)
