# Permission Client

The `PermissionClient` is an async HTTP client for Sentinel's Zanzibar-style permission API. It provides entity-level access control beyond workspace roles, allowing you to check, register, and query permissions on individual resources.

## Overview

The permission system works alongside workspace roles:

- **Workspace roles** (via JWT) control broad access -- "Can this user create documents in this workspace?"
- **Entity ACLs** (via PermissionClient) control fine-grained access -- "Can this user view this specific document?"

## Setup

```python
from sentinel_auth.permissions import PermissionClient

permissions = PermissionClient(
    base_url="http://sentinel:9003",
    service_name="my-service",
    service_key="sk_my_service_key",
)
```

### Constructor Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `base_url` | `str` | Yes | Base URL of the Sentinel service (trailing slashes are stripped) |
| `service_name` | `str` | Yes | Your service's registered name (e.g., `"docu-store"`, `"my-service"`) |
| `service_key` | `str \| None` | No | Service API key for authenticated requests. Required for `register_resource` and recommended for all calls |

## Context Manager

The client manages an internal `httpx.AsyncClient`. Use it as an async context manager to ensure proper cleanup:

```python
async with PermissionClient(
    base_url="http://sentinel:9003",
    service_name="my-service",
    service_key="sk_my_service_key",
) as client:
    allowed = await client.can(token, "document", doc_id, "view")
    # httpx client is closed automatically on exit
```

For long-lived clients, call `close()` explicitly during shutdown (or use the [`Sentinel` autoconfig](autoconfig.md) which handles this automatically):

```python
# In your FastAPI lifespan
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.permissions = PermissionClient(
        base_url="http://sentinel:9003",
        service_name="my-service",
        service_key="sk_my_service_key",
    )
    yield
    await app.state.permissions.close()

app = FastAPI(lifespan=lifespan)
```

## Methods

### `can` -- Check a Single Permission

Check whether the current user can perform an action on a specific resource.

**Signature:**

```python
async def can(
    self,
    token: str,
    resource_type: str,
    resource_id: uuid.UUID,
    action: str,
) -> bool
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `token` | `str` | The user's JWT access token |
| `resource_type` | `str` | Type of resource (e.g., `"document"`, `"project"`, `"collection"`) |
| `resource_id` | `UUID` | Unique identifier of the resource |
| `action` | `str` | Action to check -- `"view"` or `"edit"` |

**Returns:** `True` if the user is allowed, `False` otherwise.

**Example:**

```python
from uuid import UUID

from fastapi import Depends, HTTPException
from sentinel_auth.dependencies import get_current_user, get_token
from sentinel_auth.types import AuthenticatedUser


@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: UUID,
    token: str = Depends(get_token),
    user: AuthenticatedUser = Depends(get_current_user),
):
    allowed = await permissions.can(token, "document", doc_id, "view")
    if not allowed:
        raise HTTPException(status_code=403, detail="You do not have access to this document")
    return await fetch_document(doc_id)
```

### `check` -- Batch Check Permissions

Check multiple permissions in a single request. More efficient than calling `can` in a loop.

**Signature:**

```python
async def check(
    self,
    token: str,
    checks: list[PermissionCheck],
) -> list[PermissionResult]
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `token` | `str` | The user's JWT access token |
| `checks` | `list[PermissionCheck]` | List of permission checks to evaluate |

**`PermissionCheck` fields:**

| Field | Type | Description |
|-------|------|-------------|
| `service_name` | `str` | Service that owns the resource |
| `resource_type` | `str` | Type of resource |
| `resource_id` | `UUID` | Resource identifier |
| `action` | `str` | Action to check |

**`PermissionResult` fields:**

| Field | Type | Description |
|-------|------|-------------|
| `service_name` | `str` | Service that owns the resource |
| `resource_type` | `str` | Type of resource |
| `resource_id` | `UUID` | Resource identifier |
| `action` | `str` | Action that was checked |
| `allowed` | `bool` | Whether the action is permitted |

**Returns:** A list of `PermissionResult` objects.

**Example:**

```python
from sentinel_auth.dependencies import get_token
from sentinel_auth.permissions import PermissionCheck


@router.post("/documents/batch-check")
async def check_access(
    doc_ids: list[UUID],
    token: str = Depends(get_token),
    user: AuthenticatedUser = Depends(get_current_user),
):
    checks = [
        PermissionCheck(
            service_name="my-service",
            resource_type="document",
            resource_id=doc_id,
            action="view",
        )
        for doc_id in doc_ids
    ]
    results = await permissions.check(token, checks)
    return {
        str(r.resource_id): r.allowed
        for r in results
    }
```

### `register_resource` -- Register a New Resource

Register a resource with Sentinel so that permissions can be managed for it. This uses service-key authentication only (no user JWT needed).

**Signature:**

```python
async def register_resource(
    self,
    resource_type: str,
    resource_id: uuid.UUID,
    workspace_id: uuid.UUID,
    owner_id: uuid.UUID,
    visibility: str = "workspace",
) -> dict
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `resource_type` | `str` | *required* | Type of resource (e.g., `"document"`) |
| `resource_id` | `UUID` | *required* | Unique identifier of the resource |
| `workspace_id` | `UUID` | *required* | Workspace the resource belongs to |
| `owner_id` | `UUID` | *required* | User ID of the resource owner |
| `visibility` | `str` | `"workspace"` | Visibility level -- `"private"` or `"workspace"` |

**Visibility levels:**

| Level | Who can access |
|-------|---------------|
| `"private"` | Only the owner and explicitly shared users |
| `"workspace"` | All members of the workspace (default) |

**Returns:** The registered resource metadata as a dict.

**Example:**

```python
@router.post("/documents")
async def create_document(
    body: CreateDocumentRequest,
    user: AuthenticatedUser = Depends(require_role("editor")),
):
    # Create the document in your database
    document = await create_doc(body, user)

    # Register it with Sentinel
    await permissions.register_resource(
        resource_type="document",
        resource_id=document.id,
        workspace_id=user.workspace_id,
        owner_id=user.user_id,
        visibility="workspace",
    )

    return document
```

### `accessible` -- List Accessible Resources

Retrieve the list of resource IDs that a user can access. Use this to filter query results to only include resources the user is authorized to see.

**Signature:**

```python
async def accessible(
    self,
    token: str,
    resource_type: str,
    action: str,
    workspace_id: uuid.UUID,
    limit: int | None = None,
) -> tuple[list[uuid.UUID], bool]
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `token` | `str` | *required* | The user's JWT access token |
| `resource_type` | `str` | *required* | Type of resource to query |
| `action` | `str` | *required* | Action to check (`"view"` or `"edit"`) |
| `workspace_id` | `UUID` | *required* | Workspace to scope the lookup to |
| `limit` | `int \| None` | `None` | Maximum number of resource IDs to return |

**Returns:** A tuple of `(resource_ids, has_full_access)`.

- `resource_ids` -- list of UUIDs the user can access
- `has_full_access` -- if `True` and no `limit` was set, `resource_ids` will be empty. This means the user can access all resources of this type (e.g., they are an admin). The caller should skip filtering entirely.

**Example:**

```python
@router.get("/documents")
async def list_documents(
    token: str = Depends(get_token),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resource_ids, has_full_access = await permissions.accessible(
        token=token,
        resource_type="document",
        action="view",
        workspace_id=user.workspace_id,
    )

    stmt = select(Document).where(Document.workspace_id == user.workspace_id)

    # Only filter by resource IDs if the user does NOT have full access
    if not has_full_access:
        stmt = stmt.where(Document.id.in_(resource_ids))

    result = await db.execute(stmt)
    return result.scalars().all()
```

## Authentication Tiers

The permission API uses different authentication requirements depending on the endpoint:

| Endpoint | Auth Required | SDK Method |
|----------|--------------|------------|
| `/permissions/check` | Service key + user JWT | `check()`, `can()` |
| `/permissions/accessible` | Service key + user JWT | `accessible()` |
| `/permissions/register` | Service key only | `register_resource()` |
| `/permissions/{id}/share` | Service key + user JWT | `share()` |

The `_headers(token)` method handles this automatically:

- When `token` is provided, it sends both `X-Service-Key` and `Authorization: Bearer <token>`
- When `token` is `None` (as in `register_resource`), it sends only `X-Service-Key`

## Error Handling

The client catches `httpx.HTTPStatusError` internally and re-raises it as `SentinelError` with a `status_code` attribute. Catch `SentinelError` for API errors and `httpx.ConnectError` / `httpx.TimeoutException` for network failures.

See [Examples — Error Handling](examples.md#error-handling) for a full pattern with `fail_open` support.

### `share` -- Share a Resource

Share a resource with a user or group. This resolves the resource by its coordinates (`service_name`, `resource_type`, `resource_id`) and then creates an ACL entry.

**Signature:**

```python
async def share(
    self,
    token: str,
    resource_type: str,
    resource_id: uuid.UUID,
    grantee_type: str,
    grantee_id: uuid.UUID,
    permission: str = "view",
) -> dict
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `token` | `str` | *required* | The user's JWT access token |
| `resource_type` | `str` | *required* | Type of resource (e.g., `"document"`) |
| `resource_id` | `UUID` | *required* | Unique identifier of the resource |
| `grantee_type` | `str` | *required* | Type of grantee -- `"user"` or `"group"` |
| `grantee_id` | `UUID` | *required* | User or group ID to share with |
| `permission` | `str` | `"view"` | Permission level to grant -- `"view"` or `"edit"` |

**Returns:** The created ACL entry as a dict.

**Example:**

```python
from uuid import UUID

from fastapi import Depends, Request
from sentinel_auth.dependencies import get_current_user, get_token
from sentinel_auth.types import AuthenticatedUser


@router.post("/documents/{doc_id}/share")
async def share_document(
    doc_id: UUID,
    target_user_id: UUID,
    token: str = Depends(get_token),
    user: AuthenticatedUser = Depends(get_current_user),
):
    result = await permissions.share(
        token=token,
        resource_type="document",
        resource_id=doc_id,
        grantee_type="user",
        grantee_id=target_user_id,
        permission="view",
    )
    return result
```

## Timeout Configuration

The client uses a default timeout of 5 seconds. The underlying `httpx.AsyncClient` is created internally. If you need to customize timeouts, you can access the client directly after construction:

```python
import httpx

client = PermissionClient(
    base_url="http://sentinel:9003",
    service_name="my-service",
    service_key="sk_key",
)
# Override the internal client with custom timeout
client._client = httpx.AsyncClient(base_url=client.base_url, timeout=10.0)
```

## Next Steps

- [Integration Guide](integration.md) -- full walkthrough of adding permissions to your service
- [Examples](examples.md) -- common permission patterns
