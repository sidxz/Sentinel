# Python SDK

```bash
pip install sentinel-auth-sdk
```

Import as `sentinel_auth`.

## What It Provides

- **`Sentinel` class** -- one-liner setup: middleware, lifespan, clients, dependencies
- **`AuthzMiddleware`** -- dual-token validation for authz mode (IdP + Sentinel tokens)
- **`JWTAuthMiddleware`** -- single JWT validation for proxy mode
- **FastAPI dependencies** -- `get_current_user`, `require_role()`, `require_action()`, `get_auth`
- **`PermissionClient`** -- Zanzibar-style entity ACLs (check, register, share, accessible)
- **`RoleClient`** -- RBAC action registration and checks
- **`RequestAuth`** -- per-request auth context for DDD integration
- **Type definitions** -- `AuthenticatedUser`, `WorkspaceContext`, `SentinelError`

## Minimal Example

```python
from fastapi import Depends, FastAPI
from sentinel_auth import Sentinel
from sentinel_auth.types import AuthenticatedUser

sentinel = Sentinel(
    base_url="http://localhost:9003",
    service_name="my-service",
    service_key="sk_...",
    idp_jwks_url="https://www.googleapis.com/oauth2/v3/certs",
)

app = FastAPI(lifespan=sentinel.lifespan)
sentinel.protect(app)

@app.get("/me")
async def me(user: AuthenticatedUser = Depends(sentinel.require_user)):
    return {"email": user.email, "role": user.workspace_role}
```

## Requirements

| Detail       | Value              |
|--------------|--------------------|
| Python       | >= 3.12            |
| PyPI name    | `sentinel-auth-sdk` |
| Import name  | `sentinel_auth`    |

Key dependencies: `pyjwt[crypto]`, `httpx`, `starlette`, `fastapi`.

## Pages

- [Sentinel Class](sentinel-class.md) -- constructor, modes, lifespan, properties
- [Middleware](middleware.md) -- AuthzMiddleware and JWTAuthMiddleware
- [FastAPI Dependencies](dependencies.md) -- dependency injection helpers
- [PermissionClient](permissions.md) -- entity-level access control
- [RoleClient](roles.md) -- RBAC action checks
- [DDD / Clean Architecture](ddd.md) -- integration with layered architectures
