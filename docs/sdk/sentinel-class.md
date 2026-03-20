# Sentinel Class

The `Sentinel` class is the recommended entry point. It wires middleware, creates clients, registers RBAC actions on startup, and cleans up on shutdown.

```python
from sentinel_auth import Sentinel

sentinel = Sentinel(
    base_url="http://localhost:9003",
    service_name="my-service",
    service_key="sk_...",
    idp_jwks_url="https://www.googleapis.com/oauth2/v3/certs",
)
```

## Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | required | Root URL of the Sentinel service |
| `service_name` | `str` | required | Service name registered in Sentinel admin |
| `service_key` | `str` | required | Service API key from admin panel |
| `mode` | `str` | `"authz"` | `"authz"` or `"proxy"` |
| `idp_public_key` | `str \| None` | `None` | PEM public key for IdP token validation |
| `idp_jwks_url` | `str \| None` | `None` | JWKS endpoint for IdP token validation (preferred -- handles key rotation) |
| `actions` | `list[dict] \| None` | `None` | RBAC actions to register on startup |
| `allowed_workspaces` | `set[str] \| None` | `None` | Workspace IDs permitted to access this service. `None` allows all. Proxy mode only. |
| `cache_ttl` | `float` | `0` | Seconds to cache `accessible()` and `can()` results in the `PermissionClient`. `0` disables caching. Recommended: `30`–`120` for apps where permission changes are infrequent. Write operations (share, unshare, visibility changes) automatically invalidate the cache. |

In authz mode, one of `idp_public_key` or `idp_jwks_url` is required.

## AuthZ Mode (Default)

Your app authenticates users directly with the IdP. Sentinel issues an authorization-only JWT. The middleware validates both tokens on each request.

```python
sentinel = Sentinel(
    base_url="https://sentinel.example.com",
    service_name="my-service",
    service_key="sk_...",
    idp_jwks_url="https://www.googleapis.com/oauth2/v3/certs",
    actions=[
        {"action": "reports:export", "description": "Export reports"},
        {"action": "reports:delete"},
    ],
)

app = FastAPI(lifespan=sentinel.lifespan)
sentinel.protect(app)
```

Requests must send two tokens:

- `Authorization: Bearer <idp_token>`
- `X-Authz-Token: <sentinel_authz_token>`

## Proxy Mode

Sentinel handles the entire OAuth flow and issues a single JWT with both identity and authorization claims.

```python
sentinel = Sentinel(
    base_url="https://sentinel.example.com",
    service_name="my-service",
    service_key="sk_...",
    mode="proxy",
    allowed_workspaces={"uuid-1", "uuid-2"},  # optional
)

app = FastAPI(lifespan=sentinel.lifespan)
sentinel.protect(app)
```

Requests send one token: `Authorization: Bearer <sentinel_jwt>`.

## `protect(app, exclude_paths=None)`

Adds authentication middleware to the FastAPI app.

- **AuthZ mode**: adds `AuthzMiddleware` (dual-token validation)
- **Proxy mode**: adds `JWTAuthMiddleware` (single JWT validation)

```python
sentinel.protect(app, exclude_paths=["/health", "/docs", "/openapi.json", "/webhooks"])
```

Default excluded paths: `["/health", "/docs", "/openapi.json"]`.

Can be called at module level before the lifespan runs -- in authz mode, the middleware reads keys lazily from the Sentinel instance.

## Lifespan

`sentinel.lifespan` is an async context manager factory for `FastAPI(lifespan=...)`.

**On startup:**

- AuthZ mode: fetches Sentinel's public key from its JWKS endpoint
- Registers RBAC actions if `actions` was provided

**On shutdown:**

- Closes all HTTP clients (`PermissionClient`, `RoleClient`, `AuthzClient`)

```python
app = FastAPI(lifespan=sentinel.lifespan)
```

## Properties

### `sentinel.permissions` -> `PermissionClient`

Lazily-created client for entity-level ACL operations. See [PermissionClient](permissions.md).

```python
allowed = await sentinel.permissions.can(token, "document", doc_id, "view")
```

### `sentinel.roles` -> `RoleClient`

Lazily-created client for RBAC operations. See [RoleClient](roles.md).

```python
allowed = await sentinel.roles.check_action(token, "reports:export", workspace_id)
```

### `sentinel.authz` -> `AuthzClient`

Lazily-created client for the authz token exchange endpoint.

## Dependencies

### `sentinel.require_user`

FastAPI dependency returning `AuthenticatedUser`. Raises 401 if not authenticated.

```python
@app.get("/me")
async def me(user: AuthenticatedUser = Depends(sentinel.require_user)):
    return {"email": user.email}
```

### `sentinel.get_auth`

FastAPI dependency returning `RequestAuth` -- a per-request context bundling the user, token, and wired-in clients. Useful for passing auth context into service/domain layers.

```python
@app.post("/documents")
async def create(body: CreateDoc, auth: RequestAuth = Depends(sentinel.get_auth)):
    await auth.register_resource("document", doc_id)
    if await auth.can("document", other_id, "view"):
        ...
```

### `sentinel.require_action(action)`

Dependency factory enforcing an RBAC action. Returns `AuthenticatedUser` or raises 403.

```python
@app.get("/reports/export")
async def export(user: AuthenticatedUser = Depends(sentinel.require_action("reports:export"))):
    ...
```
