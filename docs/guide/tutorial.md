# Tutorial: Build Your First App

This tutorial walks through building a **Team Notes** app — a FastAPI backend with a React frontend — that uses the Daikon Identity SDK for authentication, workspace isolation, role enforcement, and entity-level permissions.

The complete source code is in the `demo/` directory of this repository.

## Prerequisites

- Identity service running locally ([Installation](../getting-started/installation.md), [Quickstart](../getting-started/quickstart.md))
- Google OAuth credentials configured
- RSA key pair at `keys/private.pem` / `keys/public.pem`
- Python 3.12+ and Node.js 18+

## What You'll Build

A note-taking app that demonstrates all three authorization tiers:

| Tier | Feature | SDK API |
|------|---------|---------|
| **Workspace Roles** | Editors create notes, admins delete | `require_role("editor")` |
| **Custom RBAC** | Export requires a registered action | `require_action(client, "notes:export")` |
| **Entity ACLs** | View/edit individual notes | `PermissionClient.can()` |

---

## Step 1: Create the Backend

Create a new FastAPI project that depends on the SDK:

```toml
# demo/backend/pyproject.toml
[project]
name = "demo-team-notes"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "pydantic-settings>=2.7.0",
    "daikon-identity-sdk",
]

[tool.uv.sources]
daikon-identity-sdk = { path = "../../sdk", editable = true }
```

Install:

```bash
cd demo/backend
uv sync
```

## Step 2: Add JWT Middleware

The `JWTAuthMiddleware` validates Bearer tokens on every request and populates `request.state.user` with an `AuthenticatedUser` object.

```python
# src/main.py
from fastapi import FastAPI
from identity_sdk.middleware import JWTAuthMiddleware
from src.config import settings

PUBLIC_KEY = settings.public_key_path.read_text()

app = FastAPI(title="Team Notes")

app.add_middleware(
    JWTAuthMiddleware,
    public_key=PUBLIC_KEY,
    exclude_paths=["/health", "/docs", "/openapi.json", "/redoc"],
)
```

After this, every request (except excluded paths) must include a valid `Authorization: Bearer <token>` header.

## Step 3: First Protected Endpoint

Use `get_current_user` to access the authenticated user's JWT claims:

```python
from fastapi import Depends
from identity_sdk.dependencies import get_current_user
from identity_sdk.types import AuthenticatedUser

@app.get("/me")
async def whoami(user: AuthenticatedUser = Depends(get_current_user)):
    return {
        "user_id": str(user.user_id),
        "email": user.email,
        "name": user.name,
        "workspace_id": str(user.workspace_id),
        "workspace_role": user.workspace_role,
    }
```

The `AuthenticatedUser` dataclass gives you `user_id`, `email`, `name`, `workspace_id`, `workspace_slug`, `workspace_role`, and `groups`.

## Step 4: Workspace-Scoped Data

Use `get_workspace_id` to scope queries to the current workspace:

```python
from identity_sdk.dependencies import get_workspace_id

@app.get("/notes")
async def list_notes(workspace_id: uuid.UUID = Depends(get_workspace_id)):
    return [n for n in all_notes if n.workspace_id == workspace_id]
```

This ensures users in workspace A never see notes from workspace B — even if they share the same database.

## Step 5: Enforce Workspace Roles

Use `require_role()` to restrict endpoints by workspace role level:

```python
from identity_sdk.dependencies import require_role

@app.post("/notes", status_code=201)
async def create_note(
    body: CreateNoteRequest,
    user: AuthenticatedUser = Depends(require_role("editor")),
):
    # user is guaranteed to be at least an editor
    note = notes.create(
        title=body.title,
        content=body.content,
        workspace_id=user.workspace_id,
        owner_id=user.user_id,
    )
    return note
```

The role hierarchy is: `viewer < editor < admin < owner`. A user with `admin` role passes `require_role("editor")`.

## Step 6: Register Resources

When creating a resource that needs entity-level permissions, register it with the identity service:

```python
from identity_sdk.permissions import PermissionClient

# Initialize in app lifespan
permissions = PermissionClient(
    base_url="http://localhost:9003",
    service_name="team-notes",
    service_key="your-service-key",
)

@app.post("/notes", status_code=201)
async def create_note(
    body: CreateNoteRequest,
    user: AuthenticatedUser = Depends(require_role("editor")),
):
    note = notes.create(...)

    # Register for ACL management
    await permissions.register_resource(
        resource_type="note",
        resource_id=note.id,
        workspace_id=user.workspace_id,
        owner_id=user.user_id,
        visibility="workspace",  # visible to all workspace members
    )
    return note
```

## Step 7: Entity-Level Permissions

Check if a user can view or edit a specific resource:

```python
@app.get("/notes/{note_id}")
async def get_note(
    note_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    token: str = Depends(get_token),
):
    note = notes.get(note_id)
    if not note:
        raise HTTPException(status_code=404)

    allowed = await permissions.can(
        token=token,
        resource_type="note",
        resource_id=note_id,
        action="view",
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Access denied")

    return note
```

The permission system follows a 7-step resolution: owner check → visibility → direct user share → group share → workspace role → deny.

## Step 8: Share a Resource

Note owners can share with other users:

```python
@app.post("/notes/{note_id}/share")
async def share_note(
    note_id: uuid.UUID,
    body: ShareNoteRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    token: str = Depends(get_token),
):
    note = notes.get(note_id)
    if note.owner_id != user.user_id:
        raise HTTPException(status_code=403, detail="Only owner can share")

    # Forward to the identity service's permission share API
    await permissions._client.post(
        f"/permissions/{note_id}/share",
        json={
            "service_name": "team-notes",
            "resource_type": "note",
            "grantee_type": "user",
            "grantee_id": str(body.user_id),
            "permission": body.permission,  # "view" or "edit"
        },
        headers=permissions._headers(token),
    )
    return {"ok": True}
```

## Step 9: Custom RBAC Actions

Register service-specific actions on startup using `RoleClient`:

```python
from identity_sdk.roles import RoleClient

roles = RoleClient(
    base_url="http://localhost:9003",
    service_name="team-notes",
    service_key="your-service-key",
)

# In your app lifespan
await roles.register_actions([
    {"action": "notes:export", "description": "Export notes as JSON"},
])
```

Then protect endpoints with `require_action()`:

```python
from identity_sdk.dependencies import require_action

@app.get("/notes/export")
async def export_notes(
    user: AuthenticatedUser = Depends(require_action(roles, "notes:export")),
    workspace_id: uuid.UUID = Depends(get_workspace_id),
):
    workspace_notes = notes.list_by_workspace(workspace_id)
    return {"notes": workspace_notes}
```

An admin must create a role with the `notes:export` action and assign it to users through the admin panel before they can access this endpoint.

## Step 10: Build the Frontend

The demo frontend is a React SPA that handles OAuth login through the identity service.

### Auth Flow

1. User clicks "Sign in with Google" → navigates to `http://localhost:9003/auth/login/google`
2. After OAuth, identity service redirects to `http://localhost:9101/auth/callback?user_id=X`
3. Frontend fetches the user's workspaces: `GET /auth/workspaces?user_id=X`
4. User selects a workspace → `POST /auth/token` exchanges for JWT tokens
5. Tokens stored in localStorage, attached to all API calls

### Token Management

```typescript
// Attach token to every request
const token = localStorage.getItem("access_token");
const res = await fetch(`/api/notes`, {
    headers: { Authorization: `Bearer ${token}` },
});

// Auto-refresh on 401
if (res.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) return retry();
    // redirect to login
}
```

### Identity Service Config

Set `FRONTEND_URL=http://localhost:9101` in `service/.env` so the OAuth callback redirects to the demo app.

## Step 11: Run Everything

```bash
# Terminal 1: Identity service infrastructure
make infra && make start

# Terminal 2: Demo backend
cd demo/backend && uv run python -m src.main

# Terminal 3: Demo frontend
cd demo/frontend && npm run dev
```

Open [http://localhost:9101](http://localhost:9101) and sign in.

## Summary

| What | How | SDK API |
|------|-----|---------|
| Authenticate users | JWT middleware on every request | `JWTAuthMiddleware` |
| Get user context | FastAPI dependency | `get_current_user` |
| Isolate workspaces | Filter data by workspace_id | `get_workspace_id` |
| Enforce roles | Minimum role check | `require_role("editor")` |
| Register resources | On creation, register for ACLs | `permissions.register_resource()` |
| Check entity access | Per-resource permission check | `permissions.can()` |
| Share resources | Grant access to other users | Permission share API |
| Custom RBAC | Register actions, check at runtime | `require_action(client, "action")` |

## Next Steps

- [SDK Reference](../sdk/index.md) — full API documentation for all SDK modules
- [Integration Guide](../sdk/integration.md) — detailed 9-step integration reference
- [Examples](../sdk/examples.md) — common patterns and recipes
