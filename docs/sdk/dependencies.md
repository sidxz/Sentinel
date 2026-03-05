# FastAPI Dependencies

The SDK provides a set of FastAPI dependency functions that extract authentication context from `request.state` (populated by `JWTAuthMiddleware`) and inject it into your route handlers.

## Overview

| Dependency | Returns | Purpose |
|------------|---------|---------|
| `get_current_user` | `AuthenticatedUser` | Extract the full user context |
| `get_workspace_id` | `UUID` | Extract just the workspace ID |
| `get_workspace_context` | `WorkspaceContext` | Extract workspace-scoped context |
| `require_role(minimum_role)` | `AuthenticatedUser` | Enforce a minimum workspace role |
| `require_action(role_client, action)` | `AuthenticatedUser` | Enforce an RBAC action |

All dependencies are importable from `identity_sdk.dependencies`:

```python
from identity_sdk.dependencies import (
    get_current_user,
    get_workspace_id,
    get_workspace_context,
    require_action,
    require_role,
)
```

## `get_current_user`

Extracts the `AuthenticatedUser` from `request.state.user`. Raises HTTP 401 if the user is not present (i.e., the middleware did not authenticate the request).

**Signature:**

```python
def get_current_user(request: Request) -> AuthenticatedUser
```

**Usage:**

```python
from fastapi import Depends
from identity_sdk.dependencies import get_current_user
from identity_sdk.types import AuthenticatedUser


@router.get("/me")
async def get_profile(user: AuthenticatedUser = Depends(get_current_user)):
    return {
        "user_id": str(user.user_id),
        "email": user.email,
        "name": user.name,
        "workspace_id": str(user.workspace_id),
        "workspace_slug": user.workspace_slug,
        "workspace_role": user.workspace_role,
        "groups": [str(g) for g in user.groups],
    }
```

**Error response** when user is not authenticated:

```json
{"detail": "Not authenticated"}
```

Status code: 401.

## `get_workspace_id`

A convenience dependency that returns only the workspace UUID. Depends on `get_current_user` internally.

**Signature:**

```python
def get_workspace_id(
    user: AuthenticatedUser = Depends(get_current_user),
) -> uuid.UUID
```

**Usage:**

```python
from uuid import UUID

from fastapi import Depends
from identity_sdk.dependencies import get_workspace_id


@router.get("/documents")
async def list_documents(
    workspace_id: UUID = Depends(get_workspace_id),
    db: AsyncSession = Depends(get_db),
):
    # All queries should be scoped to the workspace
    stmt = select(Document).where(Document.workspace_id == workspace_id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

## `get_workspace_context`

Returns a `WorkspaceContext` dataclass containing the workspace ID, workspace slug, user ID, and role. Useful when your business logic needs workspace-scoped information without the full user object.

**Signature:**

```python
def get_workspace_context(
    user: AuthenticatedUser = Depends(get_current_user),
) -> WorkspaceContext
```

**`WorkspaceContext` fields:**

| Field | Type | Description |
|-------|------|-------------|
| `workspace_id` | `UUID` | Active workspace identifier |
| `workspace_slug` | `str` | URL-friendly workspace slug |
| `user_id` | `UUID` | Authenticated user identifier |
| `role` | `str` | User's role in this workspace |

**Usage:**

```python
from fastapi import Depends
from identity_sdk.dependencies import get_workspace_context
from identity_sdk.types import WorkspaceContext


@router.post("/documents")
async def create_document(
    body: CreateDocumentRequest,
    ctx: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
):
    document = Document(
        title=body.title,
        workspace_id=ctx.workspace_id,
        owner_id=ctx.user_id,
    )
    db.add(document)
    await db.commit()
    return document
```

## `require_role`

A dependency factory that returns a dependency function enforcing a minimum workspace role. If the user's role is below the required level, a 403 Forbidden response is returned.

**Signature:**

```python
def require_role(minimum_role: str) -> Callable
```

The `minimum_role` parameter accepts one of four values. The role hierarchy from lowest to highest is:

```
viewer < editor < admin < owner
```

**Usage:**

```python
from fastapi import Depends
from identity_sdk.dependencies import require_role
from identity_sdk.types import AuthenticatedUser


# Only editors, admins, and owners can create documents
@router.post("/documents")
async def create_document(
    body: CreateDocumentRequest,
    user: AuthenticatedUser = Depends(require_role("editor")),
):
    ...


# Only admins and owners can delete
@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: UUID,
    user: AuthenticatedUser = Depends(require_role("admin")),
):
    ...


# Only workspace owners can manage settings
@router.put("/settings")
async def update_settings(
    body: SettingsRequest,
    user: AuthenticatedUser = Depends(require_role("owner")),
):
    ...
```

**Error response** when role is insufficient:

```json
{"detail": "Requires at least 'admin' role, you have 'editor'"}
```

Status code: 403.

## `AuthenticatedUser` Properties

The `AuthenticatedUser` dataclass includes convenience properties for common role checks:

### `is_admin`

Returns `True` if the user's workspace role is `"admin"` or `"owner"`.

```python
@router.delete("/users/{user_id}")
async def remove_user(
    user_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    await remove_workspace_user(user_id)
```

### `is_editor`

Returns `True` if the user's workspace role is `"editor"`, `"admin"`, or `"owner"`.

```python
@router.put("/documents/{doc_id}")
async def update_document(
    doc_id: UUID,
    body: UpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    if not user.is_editor:
        raise HTTPException(status_code=403, detail="Editor access required")
    ...
```

### `has_role(minimum_role)`

General-purpose role check. Returns `True` if the user's role is equal to or higher than `minimum_role` in the hierarchy `viewer < editor < admin < owner`.

```python
if user.has_role("editor"):
    # User is editor, admin, or owner
    ...
```

This is the same check used internally by `require_role`.

## Composing Dependencies

You can combine multiple SDK dependencies in a single route:

```python
from uuid import UUID

from fastapi import Depends
from identity_sdk.dependencies import get_workspace_id, require_role
from identity_sdk.types import AuthenticatedUser


@router.post("/documents")
async def create_document(
    body: CreateDocumentRequest,
    user: AuthenticatedUser = Depends(require_role("editor")),
    workspace_id: UUID = Depends(get_workspace_id),
):
    # user is guaranteed to be at least an editor
    # workspace_id is extracted from the same JWT
    document = Document(
        title=body.title,
        workspace_id=workspace_id,
        owner_id=user.user_id,
    )
    ...
```

FastAPI resolves shared sub-dependencies (like `get_current_user`) only once per request, so there is no performance overhead from combining them.

## `require_action`

A dependency factory that enforces an RBAC action using the `RoleClient`. If the user does not have the required action in their current workspace, a 403 Forbidden response is returned.

**Signature:**

```python
def require_action(role_client: "RoleClient", action: str) -> Callable
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `role_client` | `RoleClient` | An initialized `RoleClient` instance |
| `action` | `str` | The action identifier to enforce (e.g., `"reports:export"`) |

**Usage:**

```python
from identity_sdk.dependencies import require_action
from identity_sdk.roles import RoleClient
from identity_sdk.types import AuthenticatedUser

roles = RoleClient(
    base_url="http://identity-service:8000",
    service_name="analytics",
    service_key="sk_my_service_key",
)


# Only users with the "reports:export" action can access this endpoint
@router.get("/reports/export")
async def export_report(
    user: AuthenticatedUser = Depends(require_action(roles, "reports:export")),
):
    return generate_report(user.workspace_id)


# Combine with workspace role checks
@router.delete("/reports/{report_id}")
async def delete_report(
    report_id: UUID,
    user: AuthenticatedUser = Depends(require_action(roles, "reports:delete")),
):
    ...
```

**Error response** when action is not permitted:

```json
{"detail": "Action 'reports:export' not permitted"}
```

Status code: 403.

**How it works:**

1. Extracts the user's JWT from the `Authorization` header
2. Calls `role_client.check_action(token, action, user.workspace_id)`
3. If the check returns `False`, raises HTTP 403
4. If allowed, returns the `AuthenticatedUser` for use in the route handler

## Next Steps

- [Permission Client](permission-client.md) -- add entity-level ACL checks beyond workspace roles
- [Role Client](role-client.md) -- RBAC action registration and checks
- [Examples](examples.md) -- common patterns using these dependencies
