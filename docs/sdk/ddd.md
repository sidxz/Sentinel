# DDD / Clean Architecture

This guide shows how to integrate the Sentinel Auth SDK into applications that follow Domain-Driven Design (DDD), Clean Architecture, or similar layered patterns — where the domain and application layers must remain framework-agnostic.

The key concept is **`RequestAuth`** — a per-request object that bundles the authenticated user with token-backed authorization methods. It satisfies any `Protocol` your application layer defines, without requiring SDK imports in your inner layers.

## The Problem

In a typical layered architecture:

```
Interfaces (FastAPI)  →  Application (Use Cases)  →  Domain (Aggregates)
```

The inner layers cannot depend on FastAPI, Starlette, or any HTTP framework. But the existing SDK integration pattern (`Depends(get_current_user)`, `Depends(get_token)`, `PermissionClient.can(token, ...)`) is tightly coupled to FastAPI's dependency injection and requires threading raw JWT tokens through your code.

**`RequestAuth` solves this** by hiding the token internally and exposing a clean, framework-agnostic interface that your use cases can consume through structural typing.

## RequestAuth Overview

`RequestAuth` wraps three things in one object:

| What | How | Used by |
|------|-----|---------|
| **User identity** | Forwarded properties: `user_id`, `workspace_id`, `workspace_role`, `email`, `name`, `groups`, `is_admin`, `is_editor` | All layers |
| **Workspace role checks** | `has_role(minimum_role)` — local check, no network call | Application layer |
| **Authorization API** | `can()`, `check_action()`, `accessible()`, `register_resource()` — calls Sentinel APIs with hidden token | Application layer |

Import it from the top-level package:

```python
from sentinel_auth import RequestAuth
```

## Setup

Use the `Sentinel` autoconfig class. The `get_auth` property returns a FastAPI dependency that creates a `RequestAuth` per request with the permission and role clients wired in.

```python
import os

from fastapi import FastAPI
from sentinel_auth import Sentinel

sentinel = Sentinel(
    base_url=os.environ["SENTINEL_URL"],
    service_name="my-service",
    service_key=os.environ["SENTINEL_SERVICE_KEY"],
    actions=[
        {"action": "documents:export", "description": "Export documents"},
        {"action": "documents:delete", "description": "Delete documents"},
    ],
)

app = FastAPI(lifespan=sentinel.lifespan)
sentinel.protect(app)
```

Then in your dependencies module:

```python
# src/interfaces/dependencies.py
from my_app.infrastructure.auth import sentinel

get_auth = sentinel.get_auth
```

## Layer-by-Layer Integration

### Application Layer — Define Your Own Port

Your application layer defines what it needs from auth as a `Protocol`. No SDK imports.

```python
# src/application/ports/auth.py
from typing import Protocol
from uuid import UUID


class AuthContext(Protocol):
    """What use cases need from the auth system."""

    @property
    def user_id(self) -> UUID: ...

    @property
    def workspace_id(self) -> UUID: ...

    @property
    def workspace_role(self) -> str: ...

    @property
    def is_admin(self) -> bool: ...

    def has_role(self, minimum_role: str) -> bool: ...

    async def can(
        self, resource_type: str, resource_id: UUID, action: str
    ) -> bool: ...

    async def accessible(
        self, resource_type: str, action: str, limit: int | None = None
    ) -> tuple[list[UUID], bool]: ...

    async def register_resource(
        self, resource_type: str, resource_id: UUID, visibility: str = ...
    ) -> dict: ...
```

`RequestAuth` satisfies this Protocol via duck typing — no adapter code needed.

!!! tip "Include only what you use"
    Your Protocol doesn't need to list every `RequestAuth` method. Only declare the properties and methods your use cases actually call. Python's structural typing handles the rest.

### Application Layer — Use Cases

Use cases accept `AuthContext` as a parameter. They never import the SDK.

```python
# src/application/use_cases/create_document.py
from my_app.application.ports.auth import AuthContext
from my_app.application.ports.repositories import DocumentRepository


class CreateDocumentUseCase:
    def __init__(self, repo: DocumentRepository):
        self.repo = repo

    async def execute(
        self, request: CreateDocumentRequest, auth: AuthContext
    ) -> Result[DocumentResponse, AppError]:
        # Tier 1: workspace role check (no network call)
        if not auth.has_role("editor"):
            return Failure(AppError("forbidden", "Requires editor role"))

        document = Document.create(
            title=request.title,
            workspace_id=auth.workspace_id,
            owner_id=auth.user_id,
        )
        await self.repo.save(document)

        # Register with Sentinel for ACL management
        await auth.register_resource(
            resource_type="document",
            resource_id=document.id,
        )

        return Success(DocumentMapper.to_response(document))
```

### Interfaces Layer — FastAPI Routes

Routes inject `RequestAuth` via `Depends` and pass it to use cases.

```python
# src/interfaces/api/routes/document_routes.py
from fastapi import APIRouter, Depends
from sentinel_auth import RequestAuth

from my_app.interfaces.dependencies import get_auth, get_container

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/", status_code=201)
async def create_document(
    body: CreateDocumentRequest,
    auth: RequestAuth = Depends(get_auth),
    container=Depends(get_container),
):
    use_case = container[CreateDocumentUseCase]
    result = await use_case.execute(request=body, auth=auth)
    ...


@router.get("/{doc_id}")
async def get_document(
    doc_id: UUID,
    auth: RequestAuth = Depends(get_auth),
    container=Depends(get_container),
):
    use_case = container[GetDocumentUseCase]
    result = await use_case.execute(doc_id=doc_id, auth=auth)
    ...
```

### Domain Layer — No Auth Awareness

The domain layer receives workspace and user IDs as plain UUIDs. It has no concept of authentication or authorization.

```python
# src/domain/aggregates/document.py

class Document(Aggregate):
    @classmethod
    def create(cls, title: str, workspace_id: UUID, owner_id: UUID) -> Document:
        doc = cls.__new__(cls)
        doc.trigger_event(
            doc.Created,
            title=title,
            workspace_id=workspace_id,
            owner_id=owner_id,
        )
        return doc
```

## Three-Tier Authorization Examples

Sentinel provides three authorization tiers. Here's how each one looks in a use case.

### Tier 1: Workspace Roles (JWT Claims)

Local check — no network call. Use for coarse-grained gating.

```python
async def execute(self, auth: AuthContext) -> Result:
    # Hierarchy: viewer < editor < admin < owner
    if not auth.has_role("editor"):
        return Failure(AppError("forbidden", "Requires editor role"))

    # Or use convenience properties:
    if not auth.is_admin:
        return Failure(AppError("forbidden", "Admin access required"))
    ...
```

### Tier 2: Custom RBAC Actions

Calls Sentinel's role API. Use for action-based permissions (e.g., "can this user export reports?").

```python
async def execute(self, auth: AuthContext) -> Result:
    # "documents:export" is a custom action assigned to roles in the admin panel
    if not await auth.check_action("documents:export"):
        return Failure(AppError("forbidden", "Export permission required"))
    ...
```

!!! note "Registering actions"
    Actions are registered on startup via the `actions` parameter on `Sentinel(...)`. They are then assigned to roles through the admin panel.

### Tier 3: Entity-Level ACLs (Zanzibar-Style)

Calls Sentinel's permission API. Use for per-resource access control.

```python
# Single resource check
async def execute(self, doc_id: UUID, auth: AuthContext) -> Result:
    if not await auth.can("document", doc_id, "edit"):
        return Failure(AppError("forbidden", "No edit access to this document"))
    ...
```

```python
# List filtering — get IDs the user can access
async def execute(self, auth: AuthContext) -> Result:
    accessible_ids, has_full_access = await auth.accessible("document", "view")

    if has_full_access:
        # Admin/owner — return all in workspace
        docs = await self.read_model.find_by_workspace(auth.workspace_id)
    else:
        # Filter to only accessible documents
        docs = await self.read_model.find_by_ids(accessible_ids, auth.workspace_id)

    return Success([DocumentMapper.to_response(d) for d in docs])
```

```python
# Register a new resource for ACL management
async def execute(self, request: CreateRequest, auth: AuthContext) -> Result:
    document = Document.create(...)
    await self.repo.save(document)

    # Owner gets full access, workspace members get view
    await auth.register_resource(
        resource_type="document",
        resource_id=document.id,
        visibility="workspace",
    )
    ...
```

## Workspace Isolation

Every query should be scoped to the current user's workspace. The workspace ID comes from the JWT and is available on `auth.workspace_id`.

```python
class ListDocumentsUseCase:
    def __init__(self, read_model: DocumentReadModel):
        self.read_model = read_model

    async def execute(self, auth: AuthContext) -> Result[list[DocumentResponse], AppError]:
        # Always scope to workspace
        docs = await self.read_model.find_by_workspace(auth.workspace_id)
        return Success([DocumentMapper.to_response(d) for d in docs])
```

For combined workspace isolation + entity-level filtering:

```python
class ListDocumentsUseCase:
    def __init__(self, read_model: DocumentReadModel):
        self.read_model = read_model

    async def execute(self, auth: AuthContext) -> Result[list[DocumentResponse], AppError]:
        accessible_ids, has_full_access = await auth.accessible("document", "view")

        if has_full_access:
            docs = await self.read_model.find_by_workspace(auth.workspace_id)
        elif accessible_ids:
            docs = await self.read_model.find_by_workspace(
                auth.workspace_id, filter_ids=accessible_ids
            )
        else:
            docs = []

        return Success([DocumentMapper.to_response(d) for d in docs])
```

## Combining Multiple Tiers

Real-world use cases often combine all three tiers:

```python
class DeleteDocumentUseCase:
    def __init__(self, repo: DocumentRepository):
        self.repo = repo

    async def execute(self, doc_id: UUID, auth: AuthContext) -> Result[None, AppError]:
        # Tier 1: Must be at least editor in the workspace
        if not auth.has_role("editor"):
            return Failure(AppError("forbidden", "Requires editor role"))

        # Tier 2: Must have the delete action assigned via RBAC
        if not await auth.check_action("documents:delete"):
            return Failure(AppError("forbidden", "Delete permission required"))

        # Tier 3: Must have edit access to THIS specific document
        if not await auth.can("document", doc_id, "edit"):
            return Failure(AppError("forbidden", "No edit access to this document"))

        document = await self.repo.get(doc_id)
        if document is None:
            return Failure(AppError("not_found", "Document not found"))

        document.delete()
        await self.repo.save(document)
        return Success(None)
```

## Testing Use Cases

Since use cases type against your own `Protocol`, testing requires no SDK, no mocks of HTTP clients, and no JWT tokens.

```python
# tests/application/test_create_document.py
from uuid import uuid4


class FakeAuth:
    """Satisfies AuthContext Protocol — no SDK import needed."""

    def __init__(self, role="editor"):
        self.user_id = uuid4()
        self.workspace_id = uuid4()
        self.workspace_role = role
        self.is_admin = role in ("admin", "owner")

    def has_role(self, minimum_role):
        hierarchy = {"viewer": 0, "editor": 1, "admin": 2, "owner": 3}
        return hierarchy.get(self.workspace_role, -1) >= hierarchy.get(minimum_role, 99)

    async def can(self, resource_type, resource_id, action):
        return True

    async def check_action(self, action):
        return True

    async def accessible(self, resource_type, action, limit=None):
        return ([], True)  # full access

    async def register_resource(self, resource_type, resource_id, visibility="workspace"):
        return {"id": "fake-perm-id"}


async def test_create_requires_editor():
    auth = FakeAuth(role="viewer")
    use_case = CreateDocumentUseCase(repo=FakeRepo())
    result = await use_case.execute(request=make_request(), auth=auth)
    assert result.is_failure
    assert "editor" in result.failure().message


async def test_create_succeeds_for_editor():
    auth = FakeAuth(role="editor")
    use_case = CreateDocumentUseCase(repo=FakeRepo())
    result = await use_case.execute(request=make_request(), auth=auth)
    assert result.is_success
    assert result.value.workspace_id == auth.workspace_id
```

!!! tip "Test forbidden paths too"
    For each authorization tier in a use case, write at least one test that verifies the denied path. Adjust the `FakeAuth` to return `False` for the relevant check.

```python
async def test_delete_denied_without_rbac_action():
    class DenyDeleteAuth(FakeAuth):
        async def check_action(self, action):
            return False  # RBAC denies

    auth = DenyDeleteAuth(role="admin")
    use_case = DeleteDocumentUseCase(repo=FakeRepo())
    result = await use_case.execute(doc_id=uuid4(), auth=auth)
    assert result.is_failure
    assert "Delete permission" in result.failure().message
```

## DI Container Guidance

`RequestAuth` is **per-request** and should NOT be registered in a singleton DI container. Instead, it flows as a method parameter:

1. FastAPI dependency (`sentinel.get_auth`) creates `RequestAuth` per-request
2. Route handler receives it via `Depends`
3. Route passes it to `use_case.execute(auth=auth)`
4. Use case types it as `AuthContext` (your own Protocol)

```python
# Infrastructure — singleton container (e.g. lagom, dependency-injector, etc.)
container = Container()
container[DocumentRepository] = MongoDocumentRepository
container[CreateDocumentUseCase] = lambda c: CreateDocumentUseCase(repo=c[DocumentRepository])
# Do NOT register RequestAuth here — it's per-request


# Route — per-request auth flows through method parameters
@router.post("/documents")
async def create(
    body: CreateDocumentRequest,
    auth: RequestAuth = Depends(get_auth),     # per-request
    container=Depends(get_container),           # singleton
):
    use_case = container[CreateDocumentUseCase]
    return await use_case.execute(request=body, auth=auth)
```

## Comparison: Before and After

=== "Before (token plumbing)"

    ```python
    @router.get("/documents/{doc_id}")
    async def get_document(
        doc_id: UUID,
        token: str = Depends(get_token),
        user: AuthenticatedUser = Depends(get_current_user),
        perms: PermissionClient = Depends(get_permissions),
    ):
        allowed = await perms.can(token, "document", doc_id, "view")
        if not allowed:
            raise HTTPException(status_code=403, detail="Access denied")
        ...
    ```

=== "After (RequestAuth)"

    ```python
    @router.get("/documents/{doc_id}")
    async def get_document(
        doc_id: UUID,
        auth: RequestAuth = Depends(get_auth),
    ):
        if not await auth.can("document", doc_id, "view"):
            raise HTTPException(status_code=403, detail="Access denied")
        ...
    ```

=== "DDD (Protocol + use case)"

    ```python
    # Route
    @router.get("/documents/{doc_id}")
    async def get_document(
        doc_id: UUID,
        auth: RequestAuth = Depends(get_auth),
        container=Depends(get_container),
    ):
        use_case = container[GetDocumentUseCase]
        return await use_case.execute(doc_id=doc_id, auth=auth)

    # Use case (no SDK import)
    class GetDocumentUseCase:
        async def execute(self, doc_id: UUID, auth: AuthContext) -> Result:
            if not await auth.can("document", doc_id, "view"):
                return Failure(AppError("forbidden", "Access denied"))
            ...
    ```

## RequestAuth API Reference

| Method / Property | Returns | Network Call | Description |
|---|---|---|---|
| `user_id` | `UUID` | No | User's unique identifier |
| `workspace_id` | `UUID` | No | Active workspace ID |
| `workspace_role` | `str` | No | Role in workspace: `viewer`, `editor`, `admin`, `owner` |
| `email` | `str` | No | User's email |
| `name` | `str` | No | User's display name |
| `groups` | `list[UUID]` | No | Group memberships |
| `is_admin` | `bool` | No | True if admin or owner |
| `is_editor` | `bool` | No | True if editor, admin, or owner |
| `has_role(min)` | `bool` | No | Hierarchical role check |
| `can(type, id, action)` | `bool` | Yes | Entity-level permission (Tier 3) |
| `check_action(action)` | `bool` | Yes | RBAC action check (Tier 2) |
| `accessible(type, action)` | `(list[UUID], bool)` | Yes | List accessible resource IDs (Tier 3) |
| `register_resource(type, id)` | `dict` | Yes | Register new resource ACL (Tier 3) |
| `user` | `AuthenticatedUser` | No | The underlying user object |

## Next Steps

- [Autoconfig](autoconfig.md) — `Sentinel` class reference including `get_auth` and `require_user`
- [Permission Client](permission-client.md) — detailed API for all permission methods
- [Role Client](role-client.md) — RBAC action registration and checking
- [Examples](examples.md) — common patterns for standard FastAPI apps
- [Integration Guide](integration.md) — step-by-step for standard FastAPI apps
