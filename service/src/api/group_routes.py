import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, get_current_user
from src.database import get_db
from src.schemas.group import GroupCreateRequest, GroupResponse, GroupUpdateRequest
from src.services import group_service

router = APIRouter(prefix="/workspaces/{workspace_id}/groups", tags=["groups"])


def _require_workspace_match(user: CurrentUser, workspace_id: uuid.UUID) -> None:
    if user.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")


def _require_role(user: CurrentUser, minimum: str) -> None:
    hierarchy = {"viewer": 0, "editor": 1, "admin": 2, "owner": 3}
    if hierarchy.get(user.workspace_role, -1) < hierarchy[minimum]:
        raise HTTPException(status_code=403, detail="Insufficient role")


@router.post("", response_model=GroupResponse, status_code=201)
async def create_group(
    workspace_id: uuid.UUID,
    body: GroupCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_workspace_match(user, workspace_id)
    _require_role(user, "admin")
    return await group_service.create_group(
        db,
        workspace_id=workspace_id,
        name=body.name,
        created_by=user.user_id,
        description=body.description,
    )


@router.get("", response_model=list[GroupResponse])
async def list_groups(
    workspace_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_workspace_match(user, workspace_id)
    return await group_service.list_groups(db, workspace_id)


@router.patch("/{group_id}", response_model=GroupResponse)
async def update_group(
    workspace_id: uuid.UUID,
    group_id: uuid.UUID,
    body: GroupUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_workspace_match(user, workspace_id)
    _require_role(user, "admin")
    return await group_service.update_group(
        db, group_id, name=body.name, description=body.description
    )


@router.delete("/{group_id}", status_code=204)
async def delete_group(
    workspace_id: uuid.UUID,
    group_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_workspace_match(user, workspace_id)
    _require_role(user, "admin")
    await group_service.delete_group(db, group_id)


@router.post("/{group_id}/members/{member_user_id}", status_code=201)
async def add_group_member(
    workspace_id: uuid.UUID,
    group_id: uuid.UUID,
    member_user_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_workspace_match(user, workspace_id)
    _require_role(user, "admin")
    await group_service.add_member(db, group_id, member_user_id)
    return {"status": "ok"}


@router.delete("/{group_id}/members/{member_user_id}", status_code=204)
async def remove_group_member(
    workspace_id: uuid.UUID,
    group_id: uuid.UUID,
    member_user_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_workspace_match(user, workspace_id)
    _require_role(user, "admin")
    await group_service.remove_member(db, group_id, member_user_id)
