"""Team Notes API routes — demonstrates all three authorization tiers."""

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request
from identity_sdk.dependencies import require_action
from identity_sdk.permissions import PermissionClient
from identity_sdk.roles import RoleClient
from identity_sdk.types import AuthenticatedUser
from pydantic import BaseModel

from src.config import settings
from src.deps import get_current_user, get_permissions, get_roles, get_token, get_workspace_id
from src.models import notes

# ---------------------------------------------------------------------------
# Module-level RoleClient for require_action() factory
# ---------------------------------------------------------------------------
role_client = RoleClient(
    base_url=settings.identity_service_url,
    service_name=settings.service_name,
    service_key=settings.service_api_key or None,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------
class CreateNoteRequest(BaseModel):
    title: str
    content: str


class UpdateNoteRequest(BaseModel):
    title: str | None = None
    content: str | None = None


class ShareNoteRequest(BaseModel):
    user_id: uuid.UUID
    permission: str = "view"  # "view" or "edit"


# ---------------------------------------------------------------------------
# User info
# ---------------------------------------------------------------------------
@router.get("/me")
async def whoami(user: AuthenticatedUser = Depends(get_current_user)):
    """Current user context from JWT."""
    return {
        "user_id": str(user.user_id),
        "email": user.email,
        "name": user.name,
        "workspace_id": str(user.workspace_id),
        "workspace_slug": user.workspace_slug,
        "workspace_role": user.workspace_role,
        "groups": [str(g) for g in user.groups],
    }


@router.get("/me/actions")
async def my_actions(
    user: AuthenticatedUser = Depends(get_current_user),
    token: str = Depends(get_token),
    roles: RoleClient = Depends(get_roles),
):
    """List all RBAC actions available to the current user."""
    actions = await roles.get_user_actions(token, user.workspace_id)
    return {"actions": actions}


# ---------------------------------------------------------------------------
# Tier 1: Workspace role — list notes (any authenticated user)
# ---------------------------------------------------------------------------
@router.get("/notes")
async def list_notes(workspace_id: uuid.UUID = Depends(get_workspace_id)):
    """List all notes in the current workspace."""
    return [asdict(n) for n in notes.list_by_workspace(workspace_id)]


# ---------------------------------------------------------------------------
# Tier 2: Custom RBAC — export notes (requires notes:export action)
# NOTE: Must be defined before /notes/{note_id} to avoid path conflict
# ---------------------------------------------------------------------------
@router.get("/notes/export")
async def export_notes(
    user: AuthenticatedUser = Depends(require_action(role_client, "notes:export")),
    workspace_id: uuid.UUID = Depends(get_workspace_id),
):
    """Export all workspace notes. Requires 'notes:export' RBAC action."""
    workspace_notes = notes.list_by_workspace(workspace_id)
    return {
        "format": "json",
        "count": len(workspace_notes),
        "notes": [asdict(n) for n in workspace_notes],
    }


# ---------------------------------------------------------------------------
# Tier 1: Workspace role — create note (editor+)
# ---------------------------------------------------------------------------
@router.post("/notes", status_code=201)
async def create_note(
    body: CreateNoteRequest,
    request: Request,
    user: AuthenticatedUser = Depends(require_role("editor")),
    permissions: PermissionClient = Depends(get_permissions),
):
    """Create a note. Requires at least 'editor' workspace role."""
    note = notes.create(
        title=body.title,
        content=body.content,
        workspace_id=user.workspace_id,
        owner_id=user.user_id,
        owner_name=user.name,
    )

    # Register with the identity service permission system
    if permissions:
        try:
            await permissions.register_resource(
                resource_type="note",
                resource_id=note.id,
                workspace_id=user.workspace_id,
                owner_id=user.user_id,
                visibility="workspace",
            )
        except Exception:
            pass  # Don't fail note creation if permission registration fails

    return asdict(note)


# ---------------------------------------------------------------------------
# Tier 3: Entity ACL — view a single note
# ---------------------------------------------------------------------------
@router.get("/notes/{note_id}")
async def get_note(
    note_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    token: str = Depends(get_token),
    permissions: PermissionClient = Depends(get_permissions),
):
    """View a note. Checks entity-level 'view' permission."""
    note = notes.get(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Entity ACL check via identity service
    if permissions:
        allowed = await permissions.can(
            token=token,
            resource_type="note",
            resource_id=note_id,
            action="view",
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="Access denied")

    return asdict(note)


# ---------------------------------------------------------------------------
# Tier 3: Entity ACL — update a note
# ---------------------------------------------------------------------------
@router.patch("/notes/{note_id}")
async def update_note(
    note_id: uuid.UUID,
    body: UpdateNoteRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    token: str = Depends(get_token),
    permissions: PermissionClient = Depends(get_permissions),
):
    """Update a note. Checks entity-level 'edit' permission."""
    note = notes.get(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if permissions:
        allowed = await permissions.can(
            token=token,
            resource_type="note",
            resource_id=note_id,
            action="edit",
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="Access denied")

    updated = notes.update(note_id, title=body.title, content=body.content)
    return asdict(updated)


# ---------------------------------------------------------------------------
# Tier 1: Workspace role — delete note (admin+)
# ---------------------------------------------------------------------------
@router.delete("/notes/{note_id}")
async def delete_note(
    note_id: uuid.UUID,
    user: AuthenticatedUser = Depends(require_role("admin")),
):
    """Delete a note. Requires at least 'admin' workspace role."""
    if not notes.delete(note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Share — owner can share a note with another user
# ---------------------------------------------------------------------------
@router.post("/notes/{note_id}/share")
async def share_note(
    note_id: uuid.UUID,
    body: ShareNoteRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    token: str = Depends(get_token),
    permissions: PermissionClient = Depends(get_permissions),
):
    """Share a note with another user. Only the note owner can share."""
    note = notes.get(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if note.owner_id != user.user_id:
        raise HTTPException(status_code=403, detail="Only the owner can share")

    if not permissions:
        raise HTTPException(status_code=501, detail="Permission service not configured")

    # Use the SDK's internal client to share via identity service
    result = await permissions._client.post(
        f"/permissions/{note_id}/share",
        json={
            "service_name": permissions.service_name,
            "resource_type": "note",
            "grantee_type": "user",
            "grantee_id": str(body.user_id),
            "permission": body.permission,
        },
        headers=permissions._headers(token),
    )
    if result.status_code >= 400:
        raise HTTPException(status_code=result.status_code, detail=result.json().get("detail", "Share failed"))

    return {"ok": True, "shared_with": str(body.user_id), "permission": body.permission}
