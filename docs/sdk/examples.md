# Examples

Common patterns for using the Sentinel Auth SDK in FastAPI applications.

## Basic Route Protection

The simplest form of authentication: require a valid JWT and extract the user.

```python
from fastapi import APIRouter, Depends
from sentinel_auth.dependencies import get_current_user
from sentinel_auth.types import AuthenticatedUser

router = APIRouter()


@router.get("/me")
async def get_profile(user: AuthenticatedUser = Depends(get_current_user)):
    return {
        "user_id": str(user.user_id),
        "email": user.email,
        "name": user.name,
        "workspace": {
            "id": str(user.workspace_id),
            "slug": user.workspace_slug,
            "role": user.workspace_role,
        },
    }
```

## Role-Based Access Control

Use `require_role` to enforce minimum role requirements on routes. The role hierarchy is `viewer < editor < admin < owner`.

```python
from uuid import UUID

from fastapi import APIRouter, Depends
from sentinel_auth.dependencies import get_current_user, require_role
from sentinel_auth.types import AuthenticatedUser

router = APIRouter(prefix="/documents")


# Any authenticated user can view
@router.get("/{doc_id}")
async def get_document(
    doc_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
):
    ...


# Editors and above can create
@router.post("/")
async def create_document(
    body: CreateDocumentRequest,
    user: AuthenticatedUser = Depends(require_role("editor")),
):
    ...


# Admins and above can delete
@router.delete("/{doc_id}")
async def delete_document(
    doc_id: UUID,
    user: AuthenticatedUser = Depends(require_role("admin")),
):
    ...


# Only owners can manage workspace settings
@router.put("/settings")
async def update_workspace_settings(
    body: SettingsRequest,
    user: AuthenticatedUser = Depends(require_role("owner")),
):
    ...
```

## Permission Check for Entity Access

Check whether the current user can access a specific resource using the permission client.

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sentinel_auth.dependencies import get_current_user, get_token
from sentinel_auth.permissions import PermissionClient
from sentinel_auth.types import AuthenticatedUser

router = APIRouter(prefix="/documents")


def get_permissions(request: Request) -> PermissionClient:
    return request.app.state.permissions


@router.get("/{doc_id}")
async def get_document(
    doc_id: UUID,
    token: str = Depends(get_token),
    user: AuthenticatedUser = Depends(get_current_user),
    perms: PermissionClient = Depends(get_permissions),
    db: AsyncSession = Depends(get_db),
):
    # Check entity-level permission
    allowed = await perms.can(token, "document", doc_id, "view")
    if not allowed:
        raise HTTPException(status_code=403, detail="Access denied")

    # Fetch and return the document
    stmt = select(Document).where(
        Document.id == doc_id,
        Document.workspace_id == user.workspace_id,
    )
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document
```

## Registering Resources on Creation

Register new resources with Sentinel so permissions can be managed for them.

```python
@router.post("/")
async def create_document(
    body: CreateDocumentRequest,
    user: AuthenticatedUser = Depends(require_role("editor")),
    perms: PermissionClient = Depends(get_permissions),
    db: AsyncSession = Depends(get_db),
):
    # Create in database
    document = Document(
        title=body.title,
        content=body.content,
        workspace_id=user.workspace_id,
        owner_id=user.user_id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Register with Sentinel for permission management
    await perms.register_resource(
        resource_type="document",
        resource_id=document.id,
        workspace_id=user.workspace_id,
        owner_id=user.user_id,
        visibility="workspace",  # All workspace members can view
    )

    return document
```

For private resources (only owner and explicitly shared users):

```python
    await perms.register_resource(
        resource_type="draft",
        resource_id=draft.id,
        workspace_id=user.workspace_id,
        owner_id=user.user_id,
        visibility="private",
    )
```

## Accessible Resource Lookup for List Filtering

When listing resources, use `accessible` to get the set of resource IDs the user can see, then filter your database query accordingly.

```python
@router.get("/")
async def list_documents(
    token: str = Depends(get_token),
    user: AuthenticatedUser = Depends(get_current_user),
    perms: PermissionClient = Depends(get_permissions),
    db: AsyncSession = Depends(get_db),
):
    # Ask Sentinel which documents this user can view
    resource_ids, has_full_access = await perms.accessible(
        token=token,
        resource_type="document",
        action="view",
        workspace_id=user.workspace_id,
    )

    # Build the base query, always scoped to workspace
    stmt = select(Document).where(Document.workspace_id == user.workspace_id)

    if not has_full_access:
        # Filter to only accessible documents
        if not resource_ids:
            # User has no access to any documents
            return []
        stmt = stmt.where(Document.id.in_(resource_ids))

    # If has_full_access is True, no additional filtering needed --
    # the user can see all documents in the workspace

    result = await db.execute(stmt.order_by(Document.created_at.desc()))
    return result.scalars().all()
```

## Combining Role and Permission Checks

Use workspace roles for coarse gating and entity permissions for fine-grained control:

```python
@router.put("/{doc_id}")
async def update_document(
    doc_id: UUID,
    body: UpdateDocumentRequest,
    token: str = Depends(get_token),
    user: AuthenticatedUser = Depends(require_role("editor")),  # Must be at least editor
    perms: PermissionClient = Depends(get_permissions),
    db: AsyncSession = Depends(get_db),
):
    # Role check passed (editor+), now check entity-level edit permission
    allowed = await perms.can(token, "document", doc_id, "edit")
    if not allowed:
        raise HTTPException(status_code=403, detail="You cannot edit this document")

    stmt = (
        update(Document)
        .where(
            Document.id == doc_id,
            Document.workspace_id == user.workspace_id,
        )
        .values(title=body.title, content=body.content)
    )
    await db.execute(stmt)
    await db.commit()
```

## Error Handling

Wrap permission client calls with proper error handling to avoid cascading failures:

```python
import logging

import httpx
from sentinel_auth.types import SentinelError

logger = logging.getLogger(__name__)


async def check_permission_safe(
    perms: PermissionClient,
    token: str,
    resource_type: str,
    resource_id: UUID,
    action: str,
    *,
    fail_open: bool = False,
) -> bool:
    """Check a permission with graceful error handling.

    Args:
        fail_open: If True, allow access when the permission service is
            unreachable. Use with caution -- only for non-sensitive reads.
    """
    try:
        return await perms.can(token, resource_type, resource_id, action)
    except SentinelError as e:
        if e.status_code == 401:
            # Token is invalid/expired -- propagate as auth error
            raise HTTPException(status_code=401, detail="Authentication expired")
        logger.error("Permission check failed: %s", e.status_code)
        if fail_open:
            return True
        raise HTTPException(status_code=502, detail="Permission service error")
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.error("Permission service unreachable: %s", e)
        if fail_open:
            return True
        raise HTTPException(status_code=502, detail="Permission service unavailable")
```

Use it in routes:

```python
@router.get("/{doc_id}")
async def get_document(
    doc_id: UUID,
    token: str = Depends(get_token),
    user: AuthenticatedUser = Depends(get_current_user),
    perms: PermissionClient = Depends(get_permissions),
):
    allowed = await check_permission_safe(
        perms, token, "document", doc_id, "view"
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Access denied")
    ...
```

## Batch Permission Checks

When you need to check permissions for multiple resources (e.g., enriching a list with access metadata):

```python
from sentinel_auth.permissions import PermissionCheck


@router.post("/documents/access-check")
async def check_document_access(
    doc_ids: list[UUID],
    token: str = Depends(get_token),
    user: AuthenticatedUser = Depends(get_current_user),
    perms: PermissionClient = Depends(get_permissions),
):
    checks = [
        PermissionCheck(
            service_name="my-service",
            resource_type="document",
            resource_id=doc_id,
            action="edit",
        )
        for doc_id in doc_ids
    ]

    results = await perms.check(token, checks)

    return {
        str(r.resource_id): {
            "can_edit": r.allowed,
        }
        for r in results
    }
```

## Application Lifespan Pattern

The recommended way to manage the `PermissionClient` lifecycle:

```python
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sentinel_auth.middleware import JWTAuthMiddleware
from sentinel_auth.permissions import PermissionClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create the permission client
    app.state.permissions = PermissionClient(
        base_url=os.environ["SENTINEL_URL"],
        service_name="my-service",
        service_key=os.environ["SENTINEL_SERVICE_KEY"],
    )
    yield
    # Shutdown: close the HTTP client
    await app.state.permissions.close()


app = FastAPI(title="My Service", lifespan=lifespan)

app.add_middleware(
    JWTAuthMiddleware,
    base_url=os.environ["SENTINEL_URL"],
    exclude_paths=["/health", "/docs", "/openapi.json"],
)
```

## Testing with Mock Auth

For unit tests, you can override the SDK dependencies to bypass real JWT validation:

```python
import uuid

from fastapi.testclient import TestClient
from sentinel_auth.dependencies import get_current_user
from sentinel_auth.types import AuthenticatedUser


def mock_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
        email="test@example.com",
        name="Test User",
        workspace_id=uuid.UUID("11111111-2222-3333-4444-555555555555"),
        workspace_slug="test-workspace",
        workspace_role="editor",
        groups=[],
    )


# Override the dependency in tests
app.dependency_overrides[get_current_user] = mock_user

client = TestClient(app)
response = client.get("/documents")
assert response.status_code == 200

# Clean up
app.dependency_overrides.clear()
```

For role-specific tests:

```python
def mock_admin() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
        email="admin@example.com",
        name="Admin User",
        workspace_id=uuid.UUID("11111111-2222-3333-4444-555555555555"),
        workspace_slug="test-workspace",
        workspace_role="admin",
        groups=[],
    )


def mock_viewer() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
        email="viewer@example.com",
        name="Viewer User",
        workspace_id=uuid.UUID("11111111-2222-3333-4444-555555555555"),
        workspace_slug="test-workspace",
        workspace_role="viewer",
        groups=[],
    )


# Test that viewers cannot create documents
app.dependency_overrides[get_current_user] = mock_viewer
response = client.post("/documents", json={"title": "Test"})
assert response.status_code == 403

# Test that admins can delete documents
app.dependency_overrides[get_current_user] = mock_admin
response = client.delete("/documents/some-id")
assert response.status_code == 200
```

## Demo Application

The Sentinel repository includes a demo application under `demo/` that shows a working integration with the SDK. It demonstrates:

- JWT middleware configuration
- Route protection with `get_current_user` and `require_role`
- Permission checks with `PermissionClient`
- Resource registration on creation
- Accessible resource filtering for list endpoints

Refer to the demo app for a complete, runnable example of all these patterns working together.
