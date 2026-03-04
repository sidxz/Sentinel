import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import require_admin
from src.database import get_db
from src.schemas.admin import (
    ActivityLogResponse,
    AdminAddUserToWorkspaceRequest,
    AdminResourcePermissionResponse,
    AdminStatsResponse,
    AdminUserDetailResponse,
    AdminUserUpdateRequest,
    AdminWorkspaceCreateRequest,
    AdminWorkspaceDetailResponse,
    CsvImportPreview,
    CsvImportResult,
    PaginatedResponse,
    WorkspaceOption,
)
from src.schemas.workspace import (
    InviteMemberRequest,
    UpdateMemberRoleRequest,
    WorkspaceMemberResponse,
    WorkspaceUpdateRequest,
)
from src.schemas.group import GroupCreateRequest, GroupUpdateRequest, GroupResponse, GroupMemberResponse
from src.schemas.permission import ShareRequest, UpdateVisibilityRequest
from src.services import admin_service, activity_service, workspace_service, group_service, permission_service

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ── Stats & Dashboard ────────────────────────────────────────────────

@router.get("/stats", response_model=AdminStatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    return await admin_service.get_stats(db)


@router.get("/activity", response_model=list[ActivityLogResponse])
async def get_activity(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await activity_service.list_recent(db, limit=limit)


@router.get("/workspaces/all", response_model=list[WorkspaceOption])
async def list_all_workspaces(db: AsyncSession = Depends(get_db)):
    return await admin_service.list_all_workspaces(db)


# ── Users ─────────────────────────────────────────────────────────────

@router.get("/users", response_model=PaginatedResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_users(db, page=page, page_size=page_size, search=search)


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
async def get_user_detail(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    user = await admin_service.get_user_detail(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{user_id}", response_model=AdminUserDetailResponse)
async def update_user(
    user_id: uuid.UUID,
    body: AdminUserUpdateRequest,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await admin_service.update_user(db, user_id, name=body.name, is_active=body.is_active)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    action = None
    if body.is_active is True:
        action = "user_activated"
    elif body.is_active is False:
        action = "user_deactivated"
    elif body.name is not None:
        action = "user_updated"

    if action:
        await activity_service.log_activity(
            db, action=action, target_type="user", target_id=user_id,
            actor_id=uuid.UUID(admin["sub"]),
        )
        await db.commit()

    return await admin_service.get_user_detail(db, user_id)


@router.post("/users/{user_id}/workspaces", status_code=201)
async def add_user_to_workspace(
    user_id: uuid.UUID,
    body: AdminAddUserToWorkspaceRequest,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        await admin_service.add_user_to_workspace(
            db, user_id, body.workspace_id, body.role,
            actor_id=uuid.UUID(admin["sub"]),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok"}


# ── Workspaces ────────────────────────────────────────────────────────

@router.get("/workspaces", response_model=PaginatedResponse)
async def list_workspaces(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_workspaces(db, page=page, page_size=page_size, search=search)


@router.post("/workspaces", response_model=AdminWorkspaceDetailResponse, status_code=201)
async def create_workspace(
    body: AdminWorkspaceCreateRequest,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    actor_id = uuid.UUID(admin["sub"])
    try:
        ws = await workspace_service.create_workspace(
            db, name=body.name, slug=body.slug, created_by=actor_id, description=body.description,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    await activity_service.log_activity(
        db, action="workspace_created", target_type="workspace", target_id=ws.id,
        actor_id=actor_id, workspace_id=ws.id, detail={"name": ws.name, "slug": ws.slug},
    )
    await db.commit()
    return await admin_service.get_workspace_detail(db, ws.id)


@router.get("/workspaces/{workspace_id}", response_model=AdminWorkspaceDetailResponse)
async def get_workspace_detail(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    detail = await admin_service.get_workspace_detail(db, workspace_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return detail


@router.patch("/workspaces/{workspace_id}", response_model=AdminWorkspaceDetailResponse)
async def update_workspace(
    workspace_id: uuid.UUID,
    body: WorkspaceUpdateRequest,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        await workspace_service.update_workspace(db, workspace_id, name=body.name, description=body.description)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await activity_service.log_activity(
        db, action="workspace_updated", target_type="workspace", target_id=workspace_id,
        actor_id=uuid.UUID(admin["sub"]), workspace_id=workspace_id,
    )
    await db.commit()
    return await admin_service.get_workspace_detail(db, workspace_id)


@router.delete("/workspaces/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: uuid.UUID,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    detail = await admin_service.get_workspace_detail(db, workspace_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Workspace not found")
    try:
        await workspace_service.delete_workspace(db, workspace_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await activity_service.log_activity(
        db, action="workspace_deleted", target_type="workspace", target_id=workspace_id,
        actor_id=uuid.UUID(admin["sub"]), detail={"name": detail["name"], "slug": detail["slug"]},
    )
    await db.commit()


# ── Workspace Members ─────────────────────────────────────────────────

@router.get("/workspaces/{workspace_id}/members", response_model=list[WorkspaceMemberResponse])
async def list_workspace_members(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    return await workspace_service.list_members(db, workspace_id)


@router.post("/workspaces/{workspace_id}/members/invite", status_code=201)
async def invite_workspace_member(
    workspace_id: uuid.UUID,
    body: InviteMemberRequest,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        m = await workspace_service.invite_member(db, workspace_id, body.email, body.role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await activity_service.log_activity(
        db, action="member_invited", target_type="user", target_id=m.user_id,
        actor_id=uuid.UUID(admin["sub"]), workspace_id=workspace_id,
        detail={"email": body.email, "role": body.role},
    )
    await db.commit()
    return {"status": "ok"}


@router.patch("/workspaces/{workspace_id}/members/{user_id}")
async def update_workspace_member_role(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    body: UpdateMemberRoleRequest,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        await workspace_service.update_member_role(db, workspace_id, user_id, body.role)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await activity_service.log_activity(
        db, action="member_role_changed", target_type="user", target_id=user_id,
        actor_id=uuid.UUID(admin["sub"]), workspace_id=workspace_id,
        detail={"role": body.role},
    )
    await db.commit()
    return {"status": "ok"}


@router.delete("/workspaces/{workspace_id}/members/{user_id}", status_code=204)
async def remove_workspace_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        await workspace_service.remove_member(db, workspace_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await activity_service.log_activity(
        db, action="member_removed", target_type="user", target_id=user_id,
        actor_id=uuid.UUID(admin["sub"]), workspace_id=workspace_id,
    )
    await db.commit()


# ── Groups ────────────────────────────────────────────────────────────

@router.get("/workspaces/{workspace_id}/groups", response_model=list[GroupResponse])
async def list_workspace_groups(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    return await group_service.list_groups(db, workspace_id)


@router.post("/workspaces/{workspace_id}/groups", response_model=GroupResponse, status_code=201)
async def create_group(
    workspace_id: uuid.UUID,
    body: GroupCreateRequest,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    actor_id = uuid.UUID(admin["sub"])
    group = await group_service.create_group(db, workspace_id, body.name, actor_id, body.description)
    await activity_service.log_activity(
        db, action="group_created", target_type="group", target_id=group.id,
        actor_id=actor_id, workspace_id=workspace_id, detail={"name": group.name},
    )
    await db.commit()
    return group


@router.patch("/groups/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: uuid.UUID,
    body: GroupUpdateRequest,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        group = await group_service.update_group(db, group_id, name=body.name, description=body.description)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await activity_service.log_activity(
        db, action="group_updated", target_type="group", target_id=group_id,
        actor_id=uuid.UUID(admin["sub"]),
    )
    await db.commit()
    return group


@router.delete("/groups/{group_id}", status_code=204)
async def delete_group(
    group_id: uuid.UUID,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        await group_service.delete_group(db, group_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await activity_service.log_activity(
        db, action="group_deleted", target_type="group", target_id=group_id,
        actor_id=uuid.UUID(admin["sub"]),
    )
    await db.commit()


@router.get("/groups/{group_id}/members", response_model=list[GroupMemberResponse])
async def list_group_members(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    return await group_service.list_group_members(db, group_id)


@router.post("/groups/{group_id}/members/{user_id}", status_code=201)
async def add_group_member(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        await group_service.add_member(db, group_id, user_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    await activity_service.log_activity(
        db, action="group_member_added", target_type="user", target_id=user_id,
        actor_id=uuid.UUID(admin["sub"]),
    )
    await db.commit()
    return {"status": "ok"}


@router.delete("/groups/{group_id}/members/{user_id}", status_code=204)
async def remove_group_member(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        await group_service.remove_member(db, group_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await activity_service.log_activity(
        db, action="group_member_removed", target_type="user", target_id=user_id,
        actor_id=uuid.UUID(admin["sub"]),
    )
    await db.commit()


# ── Permissions ───────────────────────────────────────────────────────

@router.get("/permissions", response_model=PaginatedResponse)
async def list_permissions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    workspace_id: uuid.UUID | None = Query(None),
    service_name: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_permissions(
        db, page=page, page_size=page_size,
        workspace_id=workspace_id, service_name=service_name,
    )


@router.get("/permissions/{permission_id}", response_model=AdminResourcePermissionResponse)
async def get_permission_detail(
    permission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    detail = await admin_service.get_permission_detail(db, permission_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Permission not found")
    return detail


@router.patch("/permissions/{permission_id}/visibility")
async def update_permission_visibility(
    permission_id: uuid.UUID,
    body: UpdateVisibilityRequest,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        perm = await permission_service.update_visibility(db, permission_id, body.visibility)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await activity_service.log_activity(
        db, action="permission_visibility_changed", target_type="resource_permission",
        target_id=permission_id, actor_id=uuid.UUID(admin["sub"]),
        detail={"visibility": body.visibility},
    )
    await db.commit()
    return {"status": "ok", "visibility": perm.visibility}


@router.post("/permissions/{permission_id}/share", status_code=201)
async def share_permission(
    permission_id: uuid.UUID,
    body: ShareRequest,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    actor_id = uuid.UUID(admin["sub"])
    try:
        await permission_service.share_resource(
            db, permission_id, body.grantee_type, body.grantee_id, body.permission, actor_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    await activity_service.log_activity(
        db, action="permission_shared", target_type="resource_permission",
        target_id=permission_id, actor_id=actor_id,
        detail={"grantee_type": body.grantee_type, "grantee_id": str(body.grantee_id)},
    )
    await db.commit()
    return {"status": "ok"}


@router.delete("/permissions/{permission_id}/share")
async def revoke_permission_share(
    permission_id: uuid.UUID,
    grantee_type: str = Query(...),
    grantee_id: uuid.UUID = Query(...),
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        await permission_service.revoke_share(db, permission_id, grantee_type, grantee_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await activity_service.log_activity(
        db, action="permission_revoked", target_type="resource_permission",
        target_id=permission_id, actor_id=uuid.UUID(admin["sub"]),
    )
    await db.commit()
    return {"status": "ok"}


# ── CSV Import ────────────────────────────────────────────────────────

@router.post("/import/csv/preview", response_model=CsvImportPreview)
async def csv_preview(file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8")
    return admin_service.parse_csv(content)


@router.post("/import/csv/execute", response_model=CsvImportResult)
async def csv_execute(
    file: UploadFile = File(...),
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    content = (await file.read()).decode("utf-8")
    preview = admin_service.parse_csv(content)
    return await admin_service.execute_import(
        db, preview["rows"], actor_id=uuid.UUID(admin["sub"]),
    )
