# Daikon Identity Service — Integration Guide for Consuming Apps

This document is a detailed reference for integrating the daikon-identity-service
into docu-store (or any FastAPI app). Use this when working in the docu-store repo.

## Prerequisites

1. Identity service running at `http://localhost:9003` (or configured URL)
2. JWT public key available (from identity service's `/keys/public.pem`)
3. SDK installed: `uv add daikon-identity-sdk` or editable install from `/Users/sidx/workspace/identity-service/sdk`

## Step-by-step Integration

### Step 1: Install the SDK

In docu-store's pyproject.toml:

```toml
dependencies = [
    "daikon-identity-sdk",
    # ... other deps
]

[tool.uv.sources]
daikon-identity-sdk = { path = "/Users/sidx/workspace/identity-service/sdk", editable = true }
```

### Step 2: Add JWT middleware to FastAPI app

In docu-store's main.py (or app factory):

```python
from identity_sdk.middleware import JWTAuthMiddleware

# Load the identity service's public key
PUBLIC_KEY = Path("path/to/identity-service-public.pem").read_text()
# Or fetch from identity service: GET http://localhost:9003/.well-known/jwks.json (future)

app.add_middleware(
    JWTAuthMiddleware,
    public_key=PUBLIC_KEY,
    exclude_paths=["/health", "/docs", "/openapi.json"],
)
```

### Step 3: Create dependency helpers in docu-store

In `interfaces/dependencies.py`:

```python
from identity_sdk.dependencies import get_current_user, get_workspace_id, require_role
from identity_sdk.permissions import PermissionClient
from identity_sdk.types import AuthenticatedUser

# Re-export for convenience
__all__ = ["get_current_user", "get_workspace_id", "require_role", "AuthenticatedUser"]

# Permission client singleton
_permission_client: PermissionClient | None = None

def get_permission_client() -> PermissionClient:
    global _permission_client
    if _permission_client is None:
        _permission_client = PermissionClient(
            base_url="http://localhost:9003",  # from settings
            service_name="docu-store",
        )
    return _permission_client
```

### Step 4: Update API routes to inject auth context

Before:
```python
@router.post("/artifacts")
async def create_artifact(body: CreateArtifactRequest):
    result = await use_case.execute(body)
    return result
```

After:
```python
from identity_sdk.dependencies import get_current_user, require_role
from identity_sdk.types import AuthenticatedUser

@router.post("/artifacts")
async def create_artifact(
    body: CreateArtifactRequest,
    user: AuthenticatedUser = Depends(require_role("editor")),
):
    result = await use_case.execute(
        body,
        workspace_id=user.workspace_id,
        owner_id=user.user_id,
    )
    return result
```

### Step 5: Add workspace_id + owner_id to aggregates

In `domain/aggregates/artifact.py`:

```python
class Artifact:
    def __init__(self):
        self.workspace_id: UUID | None = None
        self.owner_id: UUID | None = None

    @classmethod
    def create(cls, ..., workspace_id: UUID, owner_id: UUID) -> "Artifact":
        artifact = cls()
        artifact._apply(ArtifactCreated(
            ...,
            workspace_id=workspace_id,
            owner_id=owner_id,
        ))
        return artifact
```

Same pattern for Page aggregate.

These fields are set at creation time and are IMMUTABLE.

### Step 6: Update read model projectors

In `infrastructure/event_projectors/artifact_projector.py`:

```python
async def _handle_created(self, event: ArtifactCreated):
    await self.collection.insert_one({
        "_id": str(event.artifact_id),
        "workspace_id": str(event.workspace_id),  # NEW
        "owner_id": str(event.owner_id),            # NEW
        # ... other fields
    })
```

### Step 7: Filter all read queries by workspace_id

In `infrastructure/read_repositories/mongo_read_repository.py`:

```python
async def list_artifacts(self, workspace_id: UUID) -> list[dict]:
    cursor = self.collection.find({"workspace_id": str(workspace_id)})
    return await cursor.to_list(length=None)

async def get_artifact_by_id(self, artifact_id: UUID, workspace_id: UUID) -> dict | None:
    return await self.collection.find_one({
        "_id": str(artifact_id),
        "workspace_id": str(workspace_id),  # cross-workspace access prevented
    })
```

### Step 8: Add workspace_id to Qdrant vector stores

In all vector store implementations:

```python
# When upserting
payload = {
    "workspace_id": str(workspace_id),
    # ... other payload fields
}

# When searching
filter_conditions = models.Filter(
    must=[
        models.FieldCondition(
            key="workspace_id",
            match=models.MatchValue(value=str(workspace_id)),
        ),
        # ... other filters
    ]
)
```

### Step 9: Register resources with identity service

When an artifact/page is created, register it with the permission service:

```python
from identity_sdk.permissions import PermissionClient

async def create_artifact_use_case(self, cmd, workspace_id, owner_id):
    # ... create the aggregate, persist events ...

    # Register with identity service (fire-and-forget or background task)
    await self.permission_client.register_resource(
        token=current_token,
        resource_type="artifact",
        resource_id=artifact.id,
        workspace_id=workspace_id,
        owner_id=owner_id,
        visibility="workspace",  # default: visible to all workspace members
    )
```

### Step 10: Pipeline worker / read worker — no changes needed

Workers process events that already contain workspace_id (baked into the aggregate).
No auth needed for workers — they're internal processes.

## JWT Claims Reference

The JWT issued by the identity service contains:

| Claim | Type | Description |
|-------|------|-------------|
| `sub` | UUID string | User ID |
| `email` | string | User email |
| `name` | string | Display name |
| `wid` | UUID string | Current workspace ID |
| `wslug` | string | Workspace slug |
| `wrole` | string | Workspace role: `owner`, `admin`, `editor`, `viewer` |
| `groups` | UUID string[] | Group IDs in current workspace |
| `exp` | int | Expiry (15 min for access tokens) |
| `type` | string | `access` or `refresh` |

## SDK API Quick Reference

### Types
```python
from identity_sdk.types import AuthenticatedUser, WorkspaceContext

user.user_id        # UUID
user.email          # str
user.workspace_id   # UUID
user.workspace_slug # str
user.workspace_role # str
user.groups         # list[UUID]
user.is_admin       # bool (admin or owner)
user.is_editor      # bool (editor, admin, or owner)
user.has_role("editor")  # bool (hierarchy check)
```

### FastAPI Dependencies
```python
from identity_sdk.dependencies import (
    get_current_user,      # -> AuthenticatedUser
    get_workspace_id,      # -> UUID
    get_workspace_context, # -> WorkspaceContext
    require_role,          # -> factory: require_role("editor") -> AuthenticatedUser
)
```

### Permission Client
```python
from identity_sdk.permissions import PermissionClient

client = PermissionClient(base_url="http://localhost:9003", service_name="docu-store")
await client.can(token, "artifact", artifact_id, "edit")  # -> bool
await client.register_resource(token, "artifact", id, workspace_id, owner_id)
await client.check(token, [PermissionCheck(...), ...])  # -> list[PermissionResult]
```

## Permission Resolution Order

1. Must be workspace member (enforced by JWT — if user has a valid token with wid, they're a member)
2. Is entity owner? -> full access
3. Is workspace admin/owner? -> full access
4. Is entity workspace-visible? -> apply workspace role (viewer=view, editor=edit)
5. Check direct user shares -> grant if found
6. Check group shares -> grant if found
7. Default: deny

## Migration Strategy for Existing Data

Run a one-time script that:
1. Creates a "default" workspace + "system" user in the identity service
2. Patches all existing MongoDB documents: add `workspace_id=<default>`, `owner_id=<system>`
3. Patches all existing Qdrant point payloads: add `workspace_id=<default>`
4. Registers all existing entities with the identity service permission system

## Network Configuration

Both services must be on the same Docker network:
- Identity service: `docker compose up` in identity-service repo (port 9003)
- Docu-store: `make docker-up` in docu-store repo
- Shared network: `docu_store-network` (external, created once)
- Inside Docker, docu-store reaches identity service at `http://identity-service:9003`
- In local dev (no Docker for app), use `http://localhost:9003`
