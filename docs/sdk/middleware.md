# JWT Middleware

The `JWTAuthMiddleware` is a Starlette middleware that validates JWT access tokens on every incoming request and makes the authenticated user available to your route handlers via `request.state.user`.

## Setup

### Using a PEM public key

```python
from pathlib import Path

from fastapi import FastAPI
from sentinel_auth.middleware import JWTAuthMiddleware

app = FastAPI()

public_key = Path("keys/public.pem").read_text()

app.add_middleware(
    JWTAuthMiddleware,
    public_key=public_key,
    exclude_paths=["/health", "/docs", "/openapi.json"],
)
```

### Using base URL (recommended)

```python
from fastapi import FastAPI
from sentinel_auth.middleware import JWTAuthMiddleware

app = FastAPI()

app.add_middleware(
    JWTAuthMiddleware,
    base_url="https://identity.example.com",
    exclude_paths=["/health", "/docs", "/openapi.json"],
)
```

The JWKS endpoint is derived automatically as `{base_url}/.well-known/jwks.json`, fetched lazily on the first request, and cached. This avoids the need to distribute PEM files and supports automatic key rotation.

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str \| None` | `None` | Root URL of the Sentinel identity service. The JWKS endpoint is derived automatically. This is the recommended option. |
| `public_key` | `str \| None` | `None` | RSA public key in PEM format for air-gapped deployments where the service cannot reach Sentinel at runtime. |
| `jwks_url` | `str \| None` | `None` | Explicit JWKS endpoint URL. Use only when pointing at a non-Sentinel OIDC provider whose JWKS path differs from `/.well-known/jwks.json`. |
| `audience` | `str` | `"sentinel:access"` | Expected `aud` claim in the JWT. Tokens with a different audience are rejected. |
| `algorithm` | `str` | `"RS256"` | JWT signing algorithm. Must match Sentinel's signing configuration. |
| `exclude_paths` | `list[str] \| None` | `["/health", "/docs", "/openapi.json"]` | List of path prefixes that bypass authentication. Any request whose path starts with one of these strings is passed through without token validation. |
| `allowed_workspaces` | `set[str] \| None` | `None` | Optional set of workspace IDs permitted to access this service. `None` allows all workspaces. If set, requests with a workspace ID not in the set receive a 403 response. |

One of `base_url`, `jwks_url`, or `public_key` must be provided.

## How It Works

For every incoming request, the middleware performs the following steps:

### 1. Path Exclusion Check

If the request path starts with any prefix in `exclude_paths`, the middleware skips all authentication and passes the request through to the next handler.

```python
# These requests skip authentication entirely:
# GET /health
# GET /docs
# GET /openapi.json
# GET /docs/oauth2-redirect
```

### 2. Token Extraction

The middleware looks for the `Authorization` header with a `Bearer` prefix:

```
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
```

If the header is missing or does not start with `Bearer `, the middleware returns a 401 response immediately.

### 3. JWT Validation

The token is decoded and validated using PyJWT with the provided public key and algorithm. The middleware checks:

- **Signature** -- the token was signed by Sentinel's private key
- **Expiration** -- the `exp` claim has not passed
- **Audience** -- the `aud` claim matches the expected value (default: `"sentinel:access"`)
- **Structure** -- the token is a well-formed JWT

!!! note "Audience prevents token misuse"
    Sentinel issues three token types with distinct audiences: `"sentinel:access"`, `"sentinel:refresh"`, and `"sentinel:admin"`. The middleware rejects any token whose `aud` doesn't match, preventing refresh or admin tokens from being used as access tokens. See [JWT Tokens — Access Token Claims](../guide/jwt.md#access-token-claims) for the full claims reference.

### 4. User Context Population

On successful validation, the middleware extracts claims from the JWT payload and creates an `AuthenticatedUser` instance:

| JWT Claim | AuthenticatedUser Field | Type |
|-----------|------------------------|------|
| `sub` | `user_id` | `UUID` |
| `email` | `email` | `str` |
| `name` | `name` | `str` |
| `wid` | `workspace_id` | `UUID` |
| `wslug` | `workspace_slug` | `str` |
| `wrole` | `workspace_role` | `str` |
| `groups` | `groups` | `list[UUID]` |

The `AuthenticatedUser` is set on `request.state.user` and is available to all downstream handlers and dependencies.

## Error Responses

The middleware returns JSON error responses for authentication failures:

### Missing or Malformed Header

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{"detail": "Missing or invalid Authorization header"}
```

Returned when:
- The `Authorization` header is absent
- The header value does not start with `Bearer `

### Expired Token

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{"detail": "Token has expired"}
```

Returned when the JWT's `exp` claim is in the past. The client should use their refresh token to obtain a new access token from Sentinel.

### Invalid Token

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{"detail": "Invalid token"}
```

Returned when:
- The signature does not match the public key
- The token is malformed or cannot be decoded
- The audience claim does not match

### Workspace Not Permitted

```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{"detail": "Workspace not permitted for this service"}
```

Returned when `allowed_workspaces` is configured and the JWT's workspace ID is not in the permitted set. The token itself is valid, but the service does not serve this workspace.

## Middleware Order

When combining `JWTAuthMiddleware` with other middleware, add it **last** (so it runs first in the request pipeline). FastAPI/Starlette middleware is executed in reverse order of addition:

```python
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

# Added last = runs first
app.add_middleware(
    JWTAuthMiddleware,
    base_url="https://identity.example.com",
    exclude_paths=["/health", "/docs", "/openapi.json"],
)

# Added second = runs second
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.example.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Added first = runs last
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["api.example.com"],
)
```

Request flow: `TrustedHostMiddleware` -> `CORSMiddleware` -> `JWTAuthMiddleware` -> route handler.

## Customizing Excluded Paths

Override the defaults to include additional paths or restrict the exclusion list:

```python
app.add_middleware(
    JWTAuthMiddleware,
    base_url="https://identity.example.com",
    exclude_paths=[
        "/health",
        "/docs",
        "/openapi.json",
        "/webhooks",      # Allow unauthenticated webhook callbacks
        "/public/",       # Public asset routes
    ],
)
```

Path matching uses `str.startswith()`, so `"/public/"` matches `/public/logo.png`, `/public/styles.css`, etc.

## Restricting by Workspace

If your service should only be accessible to members of specific workspaces, pass the `allowed_workspaces` parameter:

```python
app.add_middleware(
    JWTAuthMiddleware,
    base_url="https://identity.example.com",
    allowed_workspaces={"a1b2c3d4-...", "e5f6g7h8-..."},
)
```

When set, any request with a valid JWT but a workspace ID not in the set receives a `403 Forbidden` response:

```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{"detail": "Workspace not permitted for this service"}
```

Pass `None` (the default) to allow all workspaces. This is useful for multi-tenant deployments where each service instance is locked to a specific tenant:

```python
# Read from environment (comma-separated UUIDs)
allowed = settings.allowed_workspaces  # e.g. ["uuid1", "uuid2"]
app.add_middleware(
    JWTAuthMiddleware,
    base_url=settings.sentinel_url,
    allowed_workspaces=set(allowed) or None,
)
```

## Accessing the User in Route Handlers

After the middleware runs, you can access the user directly from `request.state` or use the SDK's dependency helpers (recommended):

```python
from fastapi import Depends, Request
from sentinel_auth.dependencies import get_current_user
from sentinel_auth.types import AuthenticatedUser


# Option 1: Direct access (not recommended)
@app.get("/me")
async def me(request: Request):
    user = request.state.user
    return {"email": user.email}


# Option 2: Dependency injection (recommended)
@app.get("/me")
async def me(user: AuthenticatedUser = Depends(get_current_user)):
    return {"email": user.email}
```

The dependency approach is preferred because it provides type safety, automatic 401 responses if the user is missing, and cleaner function signatures.

## HTTPS in Production

The Python SDK logs a warning if the `JWTAuthMiddleware`, `PermissionClient`, or `RoleClient` is configured with a plain `http://` URL pointing to a non-localhost host. This is a reminder, not a hard error — but **all production traffic to Sentinel must use HTTPS** to protect tokens and credentials in transit.

!!! warning "Insecure connection warning"
    ```
    WARNING sentinel_auth - Sentinel SDK (JWTAuthMiddleware) is connecting over plain
    HTTP to identity.example.com. Use HTTPS in production to protect tokens and credentials.
    ```

## Next Steps

- [Dependencies](dependencies.md) -- use `get_current_user`, `require_role`, and other helpers
- [Permission Client](permission-client.md) -- add entity-level access control
