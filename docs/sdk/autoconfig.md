# Autoconfig (Sentinel Class)

The `Sentinel` class is a single entry point that handles client creation, middleware setup, lifespan management, and RBAC action registration in one object.

## Quick Start

```python
from fastapi import FastAPI
from sentinel_auth import Sentinel

sentinel = Sentinel(
    base_url="http://localhost:9003",
    service_name="my-service",
    service_key="sk_...",
    actions=[
        {"action": "reports:export", "description": "Export reports"},
    ],
)

app = FastAPI(lifespan=sentinel.lifespan)
sentinel.protect(app)
```

That's it. The `Sentinel` object:

1. Validates the service key (raises `ValueError` if empty)
2. Creates `PermissionClient` and `RoleClient` on first use (lazy)
3. Registers RBAC actions on startup via the lifespan
4. Closes HTTP clients on shutdown
5. Adds `JWTAuthMiddleware` using `base_url` for automatic JWKS discovery

## Constructor

```python
Sentinel(
    base_url: str,
    service_name: str,
    service_key: str,
    actions: list[dict] | None = None,
    allowed_workspaces: set[str] | None = None,
)
```

| Parameter | Description |
|-----------|-------------|
| `base_url` | Root URL of the Sentinel identity service (e.g. `http://localhost:9003`) |
| `service_name` | Service name registered in Sentinel admin panel |
| `service_key` | Service API key. **Must be non-empty** — raises `ValueError` otherwise |
| `actions` | RBAC actions to register on startup. Each dict needs `action` (str) and optionally `description` (str) |
| `allowed_workspaces` | Workspace IDs permitted to access this service. `None` allows all |

## Properties

### `sentinel.permissions`

Returns a lazily-created [`PermissionClient`](permission-client.md) configured with the same `base_url`, `service_name`, and `service_key`.

```python
allowed = await sentinel.permissions.can(
    token=token, resource_type="doc", resource_id=doc_id, action="view",
)
```

### `sentinel.roles`

Returns a lazily-created [`RoleClient`](role-client.md) configured with the same `base_url`, `service_name`, and `service_key`.

```python
actions = await sentinel.roles.get_user_actions(
    token=token, workspace_id=workspace_id,
)
```

### `sentinel.require_user`

FastAPI dependency that returns the authenticated `AuthenticatedUser`. A convenience property equivalent to importing `get_current_user` directly.

```python
from fastapi import Depends
from sentinel_auth.types import AuthenticatedUser

@router.get("/me")
async def get_profile(user: AuthenticatedUser = Depends(sentinel.require_user)):
    return {"email": user.email}
```

### `sentinel.get_auth`

FastAPI dependency that returns a [`RequestAuth`](ddd.md#requestauth-overview) for the current request. The `RequestAuth` bundles the authenticated user with token-backed authorization methods (`can`, `check_action`, `accessible`), eliminating the need to manually extract and pass JWT tokens.

```python
from fastapi import Depends
from sentinel_auth import RequestAuth

@router.get("/documents/{doc_id}")
async def get_document(doc_id: UUID, auth: RequestAuth = Depends(sentinel.get_auth)):
    if not await auth.can("document", doc_id, "view"):
        raise HTTPException(403, "Access denied")
    ...
```

This is especially useful for [DDD / Clean Architecture](ddd.md) applications where use cases receive auth context as a plain object typed against a Protocol.

### `sentinel.lifespan`

Returns an async context manager factory compatible with `FastAPI(lifespan=...)`. On startup it registers any configured RBAC `actions`. On shutdown it closes the HTTP clients.

```python
app = FastAPI(lifespan=sentinel.lifespan)
```

## Methods

### `sentinel.protect(app, exclude_paths=None)`

Adds `JWTAuthMiddleware` to the app using the same `base_url`.

```python
sentinel.protect(app, exclude_paths=["/health", "/docs", "/openapi.json"])
```

| Parameter | Description |
|-----------|-------------|
| `app` | The FastAPI application instance |
| `exclude_paths` | Path prefixes that skip JWT validation. Defaults to `["/health", "/docs", "/openapi.json"]` |

### `sentinel.require_action(action)`

Dependency factory that enforces an RBAC action via Sentinel. Returns a FastAPI dependency.

```python
from fastapi import Depends
from sentinel_auth.types import AuthenticatedUser

@router.get("/reports/export")
async def export(
    user: AuthenticatedUser = Depends(sentinel.require_action("reports:export")),
):
    ...
```

## Using Clients in Routes

Access the permission and role clients directly from the `sentinel` instance:

```python
from src.main import sentinel

@router.post("/documents", status_code=201)
async def create_document(
    body: CreateDocRequest,
    user: AuthenticatedUser = Depends(require_role("editor")),
):
    doc = create_doc(body)

    # Register resource for ACL checks
    await sentinel.permissions.register_resource(
        resource_type="document",
        resource_id=doc.id,
        workspace_id=user.workspace_id,
        owner_id=user.user_id,
        visibility="workspace",
    )

    return doc
```

## When to Use Autoconfig vs Manual Setup

Use **autoconfig** (`Sentinel` class) when:

- You want minimal boilerplate and standard defaults
- Your service uses a single Sentinel instance
- You want action registration handled automatically

Use **manual setup** when:

- You need multiple `PermissionClient` or `RoleClient` instances with different configs
- You need custom middleware ordering beyond what `protect()` provides
- You need the PEM public key directly instead of JWKS
- You have a complex lifespan with other startup/shutdown logic (you can still use the clients manually alongside your own lifespan)

## Full Example

See the [Team Notes demo app](https://github.com/sidxz/Sentinel/tree/main/demo) for a complete working example using `Sentinel` autoconfig with all three authorization tiers.
