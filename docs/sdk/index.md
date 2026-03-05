# Daikon Identity SDK

The **Daikon Identity SDK** (`daikon-identity-sdk`) is a Python package that integrates your FastAPI or Starlette service with the Daikon Identity Service. It handles JWT validation, user context extraction, role enforcement, and entity-level permission checks so you can focus on your application logic.

## What the SDK Provides

### JWT Validation Middleware

`JWTAuthMiddleware` is a Starlette middleware that intercepts every incoming request, validates the `Authorization: Bearer <token>` header against the identity service's RS256 public key, and populates `request.state.user` with an `AuthenticatedUser` instance. Excluded paths (health checks, docs) skip validation entirely.

### FastAPI Dependency Helpers

A set of injectable dependencies for FastAPI routes:

- **`get_current_user`** -- extracts the `AuthenticatedUser` from `request.state`
- **`get_workspace_id`** -- returns the active workspace UUID
- **`get_workspace_context`** -- returns a `WorkspaceContext` with workspace and user identifiers
- **`require_role`** -- dependency factory that enforces a minimum workspace role (`viewer`, `editor`, `admin`, `owner`)
- **`require_action`** -- dependency factory that enforces an RBAC action via the identity service

### Async Permission Client

`PermissionClient` is an async HTTP client for the identity service's Zanzibar-style permission API. It supports:

- Single and batch permission checks (`can`, `check`)
- Resource registration (`register_resource`)
- Accessible resource lookups for list filtering (`accessible`)
- Async context manager support for clean resource management

### Async Role Client

`RoleClient` is an async HTTP client for the identity service's RBAC API. It supports:

- Service action registration (`register_actions`)
- Action permission checks (`check_action`)
- User action queries (`get_user_actions`)
- Async context manager support for clean resource management

### Type Definitions

Immutable dataclasses representing auth context:

- **`AuthenticatedUser`** -- full user context from JWT claims (user ID, email, name, workspace, role, groups)
- **`WorkspaceContext`** -- lightweight workspace-scoped subset of user context

## Package Details

| Detail | Value |
|--------|-------|
| PyPI name | `daikon-identity-sdk` |
| Import name | `identity_sdk` |
| Python | >= 3.12 |
| License | Proprietary |

## Dependencies

The SDK depends on:

| Package | Purpose |
|---------|---------|
| `pyjwt[crypto]` >= 2.10 | JWT decoding and RS256 signature verification |
| `httpx` >= 0.28 | Async HTTP client for permission API calls |
| `cryptography` >= 44.0 | RSA key handling (via PyJWT's crypto extra) |
| `pydantic` >= 2.10 | Data validation |
| `starlette` >= 0.40 | Base middleware class |
| `fastapi` >= 0.115 | Dependency injection (`Depends`, `HTTPException`) |

## Module Overview

```
identity_sdk/
    __init__.py          # Re-exports AuthenticatedUser, WorkspaceContext, RoleClient
    types.py             # AuthenticatedUser, WorkspaceContext dataclasses
    middleware.py         # JWTAuthMiddleware
    dependencies.py      # get_current_user, get_workspace_id, get_workspace_context, require_role, require_action
    permissions.py        # PermissionClient, PermissionCheck, PermissionResult
    roles.py             # RoleClient
```

## Quick Start

```python
from pathlib import Path

from fastapi import Depends, FastAPI

from identity_sdk.dependencies import get_current_user, require_role
from identity_sdk.middleware import JWTAuthMiddleware
from identity_sdk.permissions import PermissionClient
from identity_sdk.types import AuthenticatedUser

app = FastAPI()

# 1. Add JWT middleware
public_key = Path("keys/public.pem").read_text()
app.add_middleware(
    JWTAuthMiddleware,
    public_key=public_key,
    exclude_paths=["/health", "/docs", "/openapi.json"],
)

# 2. Create permission client
permissions = PermissionClient(
    base_url="http://identity-service:8000",
    service_name="my-service",
    service_key="sk_my_service_key",
)

# 3. Use dependencies in routes
@app.get("/documents/{doc_id}")
async def get_document(
    doc_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    allowed = await permissions.can(
        token=user_token,
        resource_type="document",
        resource_id=doc_id,
        action="view",
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Access denied")
    return await fetch_document(doc_id)
```

## Next Steps

- [Installation](installation.md) -- install the SDK and configure your public key
- [Middleware](middleware.md) -- configure JWT validation
- [Dependencies](dependencies.md) -- use FastAPI dependency injection for auth
- [Permission Client](permission-client.md) -- check and manage entity-level permissions
- [Role Client](role-client.md) -- RBAC action registration and checks
- [Integration Guide](integration.md) -- step-by-step walkthrough for adding auth to your service
- [Examples](examples.md) -- common patterns and recipes
