# Changelog

All notable changes to Sentinel (service, Python SDK, JS SDKs) are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) —
note that while the version is below `1.0.0`, **minor bumps may contain breaking
changes** (SemVer 0.x rule). Check the `Breaking changes` section before
upgrading.

For versions prior to `0.11.0`, see the git tag history (`git log --oneline -- service/ sdk/ sdks/`).

## [Unreleased]

<!-- Add next-version entries here -->

---

## [0.11.0] – 2026-04-17 — Security hardening

A co-ordinated fix for 17 findings across two rounds of deep security audit of
AuthZ mode (V1–V15 from round 1; V16–V18 from a follow-up round-2 review).
Core invariant reinforced: **clients cannot bypass IdP authentication**.

### Security

Each finding below is a fix. Downstream apps do not need to take action beyond
the migration steps in **Breaking changes** — no special remediation is
required on the caller side.

- **V1** — SDK middlewares (Python + Next.js) no longer skip IdP `aud` validation. Any Google/EntraID token from another OAuth client is now rejected.
- **V2** — Authz token's `svc` claim is now enforced by every consumer (server dependencies, Python middleware, Next.js middleware). Cross-service token replay is blocked.
- **V3** — `GET /authz/idp/github/login` validates `redirect_uri` against `ServiceApp.allowed_origins`. GitHub access tokens can no longer be exfiltrated to attacker-chosen sites.
- **V4** — `find_or_create_user` no longer auto-links accounts across IdPs by email. Cross-provider account takeover is blocked (see Breaking changes).
- **V6** — Authz tokens go through the same `jti` denylist + user-deactivation checks as access tokens. Captured authz tokens can now be revoked immediately, not only after their TTL.
- **V7** — `GET /auth/login/{provider}` now requires a `client_id` query parameter and binds it to the session. Authorization-code interception via redirect_uri substitution is blocked (see Breaking changes).
- **V8** — `SentinelAuthz.handleCallback()` fails closed if no login flow is in progress in the current tab. Login-CSRF injection via crafted callback URLs is blocked.
- **V9** — `AuthzLocalStorageStore` no longer persists the IdP token to `localStorage`. XSS blast radius is limited to the short-lived authz token instead of the long-lived IdP token.
- **V10** — `require_admin` re-checks `users.is_active` and `users.is_admin` on every request. Flipping either flag takes effect on the next request instead of after the cookie TTL.
- **V11** — `ClientApp.redirect_uris` is validated via `urlparse` (scheme, host, no userinfo/fragment/query, round-trip). Rejects `https://good@evil.com/cb` and similar shapes.
- **V12** — `ServiceApp.allowed_origins` has the same strict validation. Rejects `"null"`, `"*"`, paths, query strings.
- **V13** — `email_verified` IdP claim check is now strict `is True` (rejects stringified `"false"`).
- **V14** — `POST /authz/resolve` accepts an optional `nonce` — when present, must match the IdP token's nonce claim. Enables replay protection for leaked IdP tokens.
- **V15** — Demo-authz backend CORS tightened (explicit methods + headers instead of `*`).
- **V5** — `POST /authz/resolve` no longer mints authz tokens for Origin-authenticated callers. Minting now requires an `X-Service-Key`. Origin-auth is still allowed for workspace discovery (no credential issued). Closes the "browser can mint authz tokens at will as long as the IdP token is valid" window. (See Breaking changes for migration.)
- **V16** — Refresh-family revocation now blacklists the paired access token's `jti`. `token_service.store_refresh_token`'s `access_jti` slot was always empty because `auth_service.issue_tokens` and `rotate_refresh_token` never forwarded it, leaving the access-token blacklist loop in `revoke_token_family` as dead code. On theft detection, the attacker's minted access token stayed valid for up to `access_token_expire_minutes` (default 15 min) after the family was killed. Fixed by decoding the minted access JWT and plumbing its `jti` into the refresh record.
- **V17** — `GET /authz/idp/github/callback` now validates the OAuth `state` parameter against the session value stored at login start (constant-time compare, rejected first). The login endpoint generated `state` but never stored it, and the callback did not accept a `state` query parameter — the GitHub-proxy AuthZ flow had no CSRF protection on the callback. Restores parity with proxy mode (which enforces state via Authlib).
- **V18** — Proxy-mode OAuth callbacks (`/auth/callback/{provider}` and `/auth/admin/callback/{provider}`) now use the same strict `is True` `email_verified` check as authz mode. V13 patched the helper in `idp_validator.py` but the two proxy-mode callbacks used an inline `not userinfo.get("email_verified", False)` that still accepted stringified booleans. Consolidated into a single `auth_service.is_email_verified_claim` helper used by all three paths.

### Breaking changes

All breaking changes are server-side or SDK API shape. Caller code that follows
the `Before` pattern must be updated to match the `After` pattern. Each entry
also explains **Why** — useful for handling edge cases the simple patch doesn't
cover.

#### Python SDK — `sentinel_auth.Sentinel(mode="authz")` now requires `idp_audience`

**Before:**

```python
from sentinel_auth import Sentinel

sentinel = Sentinel(
    base_url="http://localhost:9003",
    service_name="my-service",
    service_key="sk_...",
    idp_jwks_url="https://www.googleapis.com/oauth2/v3/certs",
)
```

**After:**

```python
from sentinel_auth import Sentinel

sentinel = Sentinel(
    base_url="http://localhost:9003",
    service_name="my-service",
    service_key="sk_...",
    idp_jwks_url="https://www.googleapis.com/oauth2/v3/certs",
    idp_audience="123-abc.apps.googleusercontent.com",  # your OAuth client_id
    idp_issuer="https://accounts.google.com",           # recommended
)
```

**Why:** the middleware now enforces the IdP token's `aud` and (optionally) `iss` claims — without this, a signed ID token minted for *any* OAuth client of the same IdP would authenticate (including an attacker's app). The value must equal the OAuth client_id you registered with the IdP. `idp_issuer` defends against swapping the IdP entirely and is strongly recommended.

Env-var convention: `IDP_AUDIENCE` / `IDP_ISSUER` (or `GOOGLE_CLIENT_ID` for the google case).

#### Python SDK — `AuthzMiddleware` gains required `service_name` and `idp_audience`

Only affects direct users of `AuthzMiddleware` who do **not** go through `Sentinel.protect(app)` (which forwards these from the `Sentinel` instance automatically).

**Before:**

```python
app.add_middleware(
    AuthzMiddleware,
    idp_jwks_url="https://www.googleapis.com/oauth2/v3/certs",
    sentinel_public_key=sentinel_pem,
)
```

**After:**

```python
app.add_middleware(
    AuthzMiddleware,
    service_name="my-service",
    idp_audience="123-abc.apps.googleusercontent.com",
    idp_issuer="https://accounts.google.com",
    idp_jwks_url="https://www.googleapis.com/oauth2/v3/certs",
    sentinel_public_key=sentinel_pem,
)
```

**Why:** the middleware now enforces the authz token's `svc` claim equals `service_name` (cross-service replay defence) and the IdP token's `aud` equals `idp_audience` (wrong-client defence). Construction will raise `ValueError` if either argument is missing.

#### JS SDK — `new SentinelAuth(...)` (proxy mode) requires `clientId`

**Before:**

```typescript
import { SentinelAuth } from '@sentinel-auth/js'

const auth = new SentinelAuth({
  sentinelUrl: 'http://localhost:9003',
})
```

**After:**

```typescript
import { SentinelAuth } from '@sentinel-auth/js'

const auth = new SentinelAuth({
  sentinelUrl: 'http://localhost:9003',
  clientId: '00000000-0000-0000-0000-000000000000', // ClientApp UUID from admin panel
})
```

**Why:** `GET /auth/login/{provider}` now requires a `client_id` query param and validates `redirect_uri` against *that specific* ClientApp's `redirect_uris` (not any active app). Without the binding, an attacker could craft a login URL with another registered app's `redirect_uri` and intercept the auth code. The ClientApp UUID lives in the Sentinel admin panel under "Client Apps". Store it as an env var like `VITE_SENTINEL_CLIENT_ID` / `NEXT_PUBLIC_SENTINEL_CLIENT_ID`.

The `SentinelAuth` constructor throws immediately if `clientId` is missing.

#### Next.js SDK — `createSentinelAuthzMiddleware` requires `idpAudience` and `serviceName`

**Before:**

```typescript
// middleware.ts
export default createSentinelAuthzMiddleware({
  sentinelUrl: process.env.SENTINEL_URL!,
  idpJwksUrl: 'https://www.googleapis.com/oauth2/v3/certs',
  publicPaths: ['/login', '/auth/callback'],
})
```

**After:**

```typescript
// middleware.ts
export default createSentinelAuthzMiddleware({
  sentinelUrl: process.env.SENTINEL_URL!,
  idpJwksUrl: 'https://www.googleapis.com/oauth2/v3/certs',
  idpAudience: process.env.GOOGLE_CLIENT_ID!,
  idpIssuer: 'https://accounts.google.com',
  serviceName: 'my-app',
  publicPaths: ['/login', '/auth/callback'],
})
```

**Why:** same as the Python middleware — `idpAudience` is the defence against accepting tokens minted for other OAuth clients; `serviceName` is the defence against cross-service authz token replay. The factory throws at import time if either is missing.

#### Server — `GET /auth/login/{provider}` requires `client_id`

Only relevant if you call this endpoint directly (without the JS SDK, which now sets it automatically).

**Before:**

```
GET /auth/login/google?redirect_uri=https://app.example.com/callback&code_challenge=...&code_challenge_method=S256
```

**After:**

```
GET /auth/login/google?client_id=<ClientApp-UUID>&redirect_uri=https://app.example.com/callback&code_challenge=...&code_challenge_method=S256
```

**Why:** binds the flow to a specific ClientApp. `redirect_uri` is validated against that app's registered URIs only. Callback re-validates.

#### JS SDK — `SentinelAuthz` requires `mintEndpoint`; minting routes through your backend

The browser no longer calls Sentinel's `/authz/resolve` directly to mint an authz token. It POSTs to a route on your own backend, which forwards to Sentinel with the service key. Discovery (listing workspaces) still goes to Sentinel directly — only the credential-issuance step is re-routed.

**Before (0.10.x and earlier):**

```typescript
import { SentinelAuthz } from '@sentinel-auth/js'

const authz = new SentinelAuthz({
  sentinelUrl: 'http://localhost:9003',
  idps: { google: IdpConfigs.google(GOOGLE_CLIENT_ID) },
})
// selectWorkspace() POSTed directly to Sentinel's /authz/resolve
```

**After (0.11.0):**

```typescript
import { SentinelAuthz } from '@sentinel-auth/js'

const authz = new SentinelAuthz({
  sentinelUrl: 'http://localhost:9003',
  mintEndpoint: '/api/auth/mint', // <— NEW: your backend route, NOT Sentinel
  idps: { google: IdpConfigs.google(GOOGLE_CLIENT_ID) },
})
// selectWorkspace() now POSTs to `/api/auth/mint` on your origin.
// The mint endpoint MUST be same-origin to the frontend (credentials: 'same-origin')
// or absolute on a CORS-allowed origin.
```

**You also need a backend route.** FastAPI example:

```python
# your-app/routes/auth.py
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from your_app.sentinel_instance import sentinel  # the Sentinel SDK instance

router = APIRouter()

class MintRequest(BaseModel):
    idp_token: str
    provider: str
    workspace_id: uuid.UUID
    nonce: str | None = None

@router.post("/api/auth/mint")
async def mint_authz_token(body: MintRequest):
    """Proxy: browser → here → Sentinel (with service key). Never expose the key."""
    try:
        return await sentinel.authz.resolve(
            idp_token=body.idp_token,
            provider=body.provider,
            workspace_id=body.workspace_id,
            nonce=body.nonce,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**Add the route to `exclude_paths`** — it's hit before the user has a session:

```python
sentinel.protect(app, exclude_paths=[
    "/health", "/docs", "/openapi.json",
    "/api/auth/mint",  # <— NEW: login hasn't happened yet at this point
])
```

**Next.js Route Handler equivalent:**

```typescript
// app/api/auth/mint/route.ts
import { NextResponse } from 'next/server'

export async function POST(req: Request) {
  const body = await req.json()
  const r = await fetch(`${process.env.SENTINEL_URL}/authz/resolve`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Service-Key': process.env.SENTINEL_SERVICE_KEY!, // server-side env only
    },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    return NextResponse.json(await r.json(), { status: r.status })
  }
  return NextResponse.json(await r.json())
}
```

**Why:** the old flow let any code running on a registered `allowed_origin` mint authz tokens as long as it had an IdP token. In practice, an XSS during a live session could keep re-minting for the IdP token's full TTL (~1h for Google). Routing the mint through your backend closes that window: XSS is limited to replaying the authz token that's already in the store (5-min TTL). Discovery stays browser-direct because it returns no credentials.

Cost: ~20 lines of backend proxy code per frontend; one new exclude path; one config field on `SentinelAuthz`. No crypto, no token storage changes. Backward-compatible for any code that called `AuthzClient.resolve()` server-side with a service key (that's the service-key path the new mint endpoint itself uses).

#### Server — `find_or_create_user` raises `CrossProviderEmailConflict`

Callers are `/auth/callback/*` and `/authz/resolve`. The HTTP layer already handles this — the breaking change is for any code that imports and calls `find_or_create_user` directly.

**Before:**

```python
user = await auth_service.find_or_create_user(db, provider="github", provider_user_id="12345", email=email, name=name)
# If email matched an existing Google user, GitHub account was silently attached.
```

**After:**

```python
try:
    user = await auth_service.find_or_create_user(db, provider="github", provider_user_id="12345", email=email, name=name)
except auth_service.CrossProviderEmailConflict as e:
    # Email matched a user provisioned under a different IdP.
    # Ask the user to sign in with the original provider.
    return error_response(409, str(e))
```

**Why:** previous behaviour let an attacker who controlled a weaker IdP (e.g. a free personal EntraID account) impersonate a user originally provisioned from a stronger IdP (e.g. a corporate Google Workspace) as long as the emails matched. Identity is now keyed strictly on `(provider, provider_user_id)`.

Downstream impact: existing users are unaffected. Only *new* sign-ins where a different provider's email collides with an existing user are rejected.

HTTP surface:

- `POST /authz/resolve` returns `409 {"detail": "An account with email ... exists under a different identity provider..."}`
- `GET /auth/callback/{provider}` shows the "Email Already Used" HTML error page
- `GET /auth/admin/callback/{provider}` redirects with `?error=email_conflict`

### Changed

- **`AuthzLocalStorageStore` (JS SDK)** — the IdP token is now kept in instance memory only; it is no longer written to `localStorage`. The authz token and session metadata still persist. On page reload the SDK has no IdP token and treats the session as requiring re-authentication via the IdP login flow. Apps that relied on the old behaviour for silent refresh across reloads will observe a UX shift: users re-auth after reload. Apps needing true persistent sessions should front their frontend with a backend route that stores tokens server-side behind an `HttpOnly` cookie.

- **`ClientApp.redirect_uris` / `ServiceApp.allowed_origins` validation** — Pydantic now parses each entry with `urlparse` and rejects malformed shapes (no userinfo, no fragment, no query on URIs; no path/query/fragment on origins; no `"null"` / `"*"`). Existing values in the database are unaffected. `POST /admin/client-apps` / `PATCH /admin/service-apps/{id}` return `422` for bad inputs that previously passed.

- **`require_admin` (server)** — now re-reads the admin user's `is_active` + `is_admin` from the database on every admin request. Expect a small additional DB round-trip per admin API call. Demoting or deactivating an admin now takes effect on their very next request.

- **`AuthzMiddleware.__init__` (Python SDK)** — arguments are now keyword-only (`*`-prefixed). Positional calls break at import time.

### Added

- **Server** — `POST /authz/resolve` accepts an optional `nonce` field. When provided, the IdP token's `nonce` claim (OIDC only) must match. Browsers should pass the same nonce they generated at login start.
- **JS SDK** — `SentinelAuthz.handleCallback()` throws `No login flow in progress — callback rejected` when `sessionStorage.sentinel_authz_nonce` is absent. Previously silently accepted.
- **Python SDK** — `auth_service.CrossProviderEmailConflict` exception type.
- **Admin UI** — `Login.tsx` renders new error codes `?error=email_conflict` and `?error=email_not_verified`.
- **Tests** — `test_authz_middleware.py` gains `test_wrong_audience_rejected` and `test_wrong_svc_rejected`.

### Fixed

- IdP `email_verified` check no longer accepts stringified `"false"` (a truthy non-empty string).
- Admin tokens now obey the user-deactivation denylist.
- GitHub proxy callback re-validates `redirect_uri` against the allowlist on return, not only at login start.

### Migration for downstream apps (quick checklist)

1. **Bump Sentinel SDK versions** everywhere Sentinel is used:
   - `pip install -U sentinel-auth-sdk` (Python)
   - `npm install @sentinel-auth/js@^0.11 @sentinel-auth/react@^0.11 @sentinel-auth/nextjs@^0.11` (JS)
2. **JS proxy-mode frontends** (`SentinelAuth`): add `clientId` from env (source: Sentinel admin panel → Client Apps).
3. **JS authz-mode frontends** (`SentinelAuthz`): add `mintEndpoint` (new backend route — see the breaking-changes entry above). Ship the backend route and add its path to `sentinel.protect(app, exclude_paths=[...])`.
4. **Python authz-mode backends**: add `idp_audience` (your OAuth client_id) and `idp_issuer` to the `Sentinel(...)` constructor.
5. **Next.js authz middlewares**: add `idpAudience`, `idpIssuer`, `serviceName` to `createSentinelAuthzMiddleware(...)`.
6. **Any direct callers of `find_or_create_user`**: catch `CrossProviderEmailConflict`.
7. **If `AuthzLocalStorageStore` is used**: UX will require re-auth after page reload. If that's unacceptable, design a server-backed cookie store.
8. **Admin-panel-registered ClientApps / ServiceApps**: existing records unaffected. New admin panel submissions with trailing slashes, paths, or malformed shapes will now 422 — tighten input.

### Known deferred

_None at this release — V5 was originally deferred but is now included (see the `SentinelAuthz` requires `mintEndpoint` breaking-change entry)._
