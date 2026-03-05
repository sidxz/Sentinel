# Role Client

The `RoleClient` is an async HTTP client for the identity service's RBAC API. It allows services to register actions, check user permissions, and query available actions -- providing action-based authorization beyond workspace roles.

## Overview

The RBAC system works alongside workspace roles and entity ACLs:

- **Workspace roles** (via JWT) -- "Can this user create documents?" (coarse-grained)
- **Custom roles** (via RoleClient) -- "Can this user export reports?" (action-based)
- **Entity ACLs** (via PermissionClient) -- "Can this user view document X?" (per-resource)

## Setup

```python
from identity_sdk.roles import RoleClient

roles = RoleClient(
    base_url="http://identity-service:8000",
    service_name="my-service",
    service_key="sk_my_service_key",
)
```

### Constructor Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `base_url` | `str` | Yes | Base URL of the identity service (trailing slashes are stripped) |
| `service_name` | `str` | Yes | Your service's registered name (e.g., `"analytics"`, `"docu-store"`) |
| `service_key` | `str \| None` | No | Service API key for authenticated requests |

## Context Manager

The client manages an internal `httpx.AsyncClient`. Use it as an async context manager to ensure proper cleanup:

```python
async with RoleClient(
    base_url="http://identity-service:8000",
    service_name="my-service",
    service_key="sk_my_service_key",
) as client:
    allowed = await client.check_action(token, "reports:export", workspace_id)
```

For long-lived clients, call `close()` explicitly during shutdown:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.roles = RoleClient(
        base_url="http://identity-service:8000",
        service_name="my-service",
        service_key="sk_my_service_key",
    )
    yield
    await app.state.roles.close()
```

## Methods

### `register_actions` -- Register Service Actions

Registers actions for this service. This is idempotent -- existing actions get their descriptions updated, new actions are created. Uses service-key authentication only (no user JWT needed).

**Signature:**

```python
async def register_actions(self, actions: list[dict]) -> dict
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `actions` | `list[dict]` | List of action definitions. Each dict has `"action"` (str, required) and `"description"` (str, optional) |

**Returns:** The list of registered action objects.

**Example:**

```python
# Register during application startup
await roles.register_actions([
    {"action": "reports:export", "description": "Export reports as CSV/PDF"},
    {"action": "reports:view", "description": "View report data"},
    {"action": "dashboards:create", "description": "Create new dashboards"},
])
```

### `check_action` -- Check a Single Action

Check whether the current user can perform an action in a workspace.

**Signature:**

```python
async def check_action(
    self,
    token: str,
    action: str,
    workspace_id: uuid.UUID,
) -> bool
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `token` | `str` | The user's JWT access token |
| `action` | `str` | Action to check (e.g., `"reports:export"`) |
| `workspace_id` | `UUID` | Workspace to check within |

**Returns:** `True` if the user is allowed, `False` otherwise.

**Example:**

```python
from fastapi import Depends, HTTPException, Request
from identity_sdk.dependencies import get_current_user
from identity_sdk.types import AuthenticatedUser


@router.get("/reports/export")
async def export_report(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    token = request.headers["Authorization"].removeprefix("Bearer ")
    allowed = await roles.check_action(token, "reports:export", user.workspace_id)
    if not allowed:
        raise HTTPException(status_code=403, detail="Not authorized to export reports")
    return generate_report()
```

### `get_user_actions` -- List User's Actions

Retrieve all actions the current user can perform for this service in a workspace.

**Signature:**

```python
async def get_user_actions(
    self,
    token: str,
    workspace_id: uuid.UUID,
) -> list[str]
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `token` | `str` | The user's JWT access token |
| `workspace_id` | `UUID` | Workspace to query |

**Returns:** List of action strings the user can perform.

**Example:**

```python
@router.get("/user/capabilities")
async def get_capabilities(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    token = request.headers["Authorization"].removeprefix("Bearer ")
    actions = await roles.get_user_actions(token, user.workspace_id)
    return {"actions": actions}
    # → {"actions": ["reports:export", "reports:view", "dashboards:create"]}
```

## Authentication Tiers

| Endpoint | Auth Required | SDK Method |
|----------|--------------|------------|
| `/roles/actions/register` | Service key only | `register_actions()` |
| `/roles/check-action` | Service key + user JWT | `check_action()` |
| `/roles/user-actions` | Service key + user JWT | `get_user_actions()` |

The `_headers(token)` method handles this automatically -- same pattern as `PermissionClient`.

## Error Handling

The client raises `httpx.HTTPStatusError` on non-2xx responses:

```python
import httpx


async def safe_action_check(token: str, action: str, workspace_id: UUID) -> bool:
    try:
        return await roles.check_action(token, action, workspace_id)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise HTTPException(status_code=401, detail="Token expired or invalid")
        if e.response.status_code == 403:
            return False  # Cross-workspace check
        raise HTTPException(status_code=502, detail="Role service unavailable")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Role service unavailable")
```

## Next Steps

- [Dependencies](dependencies.md) -- use `require_action` for declarative action enforcement
- [Custom Roles Guide](../guide/roles.md) -- full RBAC system documentation
- [Permission Client](permission-client.md) -- entity-level ACL checks
