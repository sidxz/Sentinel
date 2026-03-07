# Role Client

The `RoleClient` is an async HTTP client for Sentinel's RBAC API. It allows services to register actions, check user permissions, and query available actions -- providing action-based authorization beyond workspace roles.

## Overview

The RBAC system works alongside workspace roles and entity ACLs:

- **Workspace roles** (via JWT) -- "Can this user create documents?" (coarse-grained)
- **Custom roles** (via RoleClient) -- "Can this user export reports?" (action-based)
- **Entity ACLs** (via PermissionClient) -- "Can this user view document X?" (per-resource)

## Setup

```python
from sentinel_auth.roles import RoleClient

roles = RoleClient(
    base_url="http://sentinel:9003",
    service_name="my-service",
    service_key="sk_my_service_key",
)
```

### Constructor Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `base_url` | `str` | Yes | Base URL of the Sentinel service (trailing slashes are stripped) |
| `service_name` | `str` | Yes | Your service's registered name (e.g., `"analytics"`, `"docu-store"`) |
| `service_key` | `str \| None` | No | Service API key for authenticated requests |

## Context Manager

The client manages an internal `httpx.AsyncClient`. Use it as an async context manager to ensure proper cleanup:

```python
async with RoleClient(
    base_url="http://sentinel:9003",
    service_name="my-service",
    service_key="sk_my_service_key",
) as client:
    allowed = await client.check_action(token, "reports:export", workspace_id)
```

For long-lived clients, call `close()` explicitly during shutdown (or use the [`Sentinel` autoconfig](autoconfig.md) which handles this automatically):

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.roles = RoleClient(
        base_url="http://sentinel:9003",
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

**Returns:** The API response as a `dict`.

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
from fastapi import Depends, HTTPException
from sentinel_auth.dependencies import get_current_user, get_token
from sentinel_auth.types import AuthenticatedUser


@router.get("/reports/export")
async def export_report(
    token: str = Depends(get_token),
    user: AuthenticatedUser = Depends(get_current_user),
):
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
    token: str = Depends(get_token),
    user: AuthenticatedUser = Depends(get_current_user),
):
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

The client catches `httpx.HTTPStatusError` internally and re-raises it as `SentinelError` with a `status_code` attribute. Catch `SentinelError` for API errors and `httpx.ConnectError` / `httpx.TimeoutException` for network failures.

See [Examples — Error Handling](examples.md#error-handling) for a full pattern.

## Next Steps

- [Dependencies](dependencies.md) -- use `require_action` for declarative action enforcement
- [Custom Roles Guide](../guide/roles.md) -- full RBAC system documentation
- [Permission Client](permission-client.md) -- entity-level ACL checks
