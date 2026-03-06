import uuid

from sqlalchemy import select, union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.permission import ResourcePermission, ResourceShare


async def register_resource(
    db: AsyncSession,
    service_name: str,
    resource_type: str,
    resource_id: uuid.UUID,
    workspace_id: uuid.UUID,
    owner_id: uuid.UUID,
    visibility: str = "workspace",
) -> ResourcePermission:
    perm = ResourcePermission(
        service_name=service_name,
        resource_type=resource_type,
        resource_id=resource_id,
        workspace_id=workspace_id,
        owner_id=owner_id,
        visibility=visibility,
    )
    db.add(perm)
    await db.commit()
    return perm


async def get_permission_by_id(
    db: AsyncSession,
    permission_id: uuid.UUID,
) -> ResourcePermission | None:
    return await db.get(ResourcePermission, permission_id)


async def get_resource_permission(
    db: AsyncSession,
    service_name: str,
    resource_type: str,
    resource_id: uuid.UUID,
) -> ResourcePermission | None:
    stmt = (
        select(ResourcePermission)
        .options(selectinload(ResourcePermission.shares))
        .where(
            ResourcePermission.service_name == service_name,
            ResourcePermission.resource_type == resource_type,
            ResourcePermission.resource_id == resource_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_visibility(
    db: AsyncSession,
    permission_id: uuid.UUID,
    visibility: str,
) -> ResourcePermission:
    stmt = (
        select(ResourcePermission)
        .options(selectinload(ResourcePermission.shares))
        .where(ResourcePermission.id == permission_id)
    )
    result = await db.execute(stmt)
    perm = result.scalar_one_or_none()
    if not perm:
        raise ValueError("Resource permission not found")
    perm.visibility = visibility
    await db.commit()
    return perm


async def share_resource(
    db: AsyncSession,
    permission_id: uuid.UUID,
    grantee_type: str,
    grantee_id: uuid.UUID,
    permission: str,
    granted_by: uuid.UUID,
) -> ResourceShare:
    share = ResourceShare(
        resource_permission_id=permission_id,
        grantee_type=grantee_type,
        grantee_id=grantee_id,
        permission=permission,
        granted_by=granted_by,
    )
    db.add(share)
    await db.commit()
    return share


async def revoke_share(
    db: AsyncSession,
    permission_id: uuid.UUID,
    grantee_type: str,
    grantee_id: uuid.UUID,
) -> None:
    stmt = select(ResourceShare).where(
        ResourceShare.resource_permission_id == permission_id,
        ResourceShare.grantee_type == grantee_type,
        ResourceShare.grantee_id == grantee_id,
    )
    result = await db.execute(stmt)
    share = result.scalar_one_or_none()
    if not share:
        raise ValueError("Share not found")
    await db.delete(share)
    await db.commit()


async def check_permission(
    db: AsyncSession,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    workspace_role: str,
    group_ids: list[uuid.UUID],
    service_name: str,
    resource_type: str,
    resource_id: uuid.UUID,
    action: str,
) -> bool:
    """
    Permission resolution:
    1. Must be workspace member (caller ensures this via JWT)
    2. Is entity owner? -> full access
    3. Is workspace admin/owner? -> full access
    4. Is entity workspace-visible? -> apply workspace role
    5. Check direct user shares
    6. Check group shares
    7. Default: deny
    """
    perm = await get_resource_permission(db, service_name, resource_type, resource_id)
    if not perm:
        return False

    # Must be in the same workspace
    if perm.workspace_id != workspace_id:
        return False

    # Owner has full access
    if perm.owner_id == user_id:
        return True

    # Workspace admin/owner has full access
    if workspace_role in ("admin", "owner"):
        return True

    # Workspace-visible: apply role-based access
    if perm.visibility == "workspace":
        if action == "view":
            return True  # All workspace members can view
        if action == "edit" and workspace_role == "editor":
            return True

    # Check direct user shares
    stmt = select(ResourceShare).where(
        ResourceShare.resource_permission_id == perm.id,
        ResourceShare.grantee_type == "user",
        ResourceShare.grantee_id == user_id,
    )
    result = await db.execute(stmt)
    user_share = result.scalar_one_or_none()
    if user_share:
        if action == "view":
            return True
        if action == "edit" and user_share.permission == "edit":
            return True

    # Check group shares
    if group_ids:
        stmt = select(ResourceShare).where(
            ResourceShare.resource_permission_id == perm.id,
            ResourceShare.grantee_type == "group",
            ResourceShare.grantee_id.in_(group_ids),
        )
        result = await db.execute(stmt)
        group_shares = result.scalars().all()
        for gs in group_shares:
            if action == "view":
                return True
            if action == "edit" and gs.permission == "edit":
                return True

    return False


async def lookup_accessible_resources(
    db: AsyncSession,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    workspace_role: str,
    group_ids: list[uuid.UUID],
    service_name: str,
    resource_type: str,
    action: str,
    limit: int | None = None,
) -> tuple[list[uuid.UUID], bool]:
    """
    Return (resource_ids, has_full_access) for the given user context.

    Admin/owner roles get has_full_access=True. If no limit is set, resource_ids
    is empty (caller should skip filtering). With a limit, returns up to that
    many IDs even for full-access users.
    """
    is_privileged = workspace_role in ("admin", "owner")

    if is_privileged and limit is None:
        return [], True

    # Base filter: same workspace, service, type
    base_filter = [
        ResourcePermission.workspace_id == workspace_id,
        ResourcePermission.service_name == service_name,
        ResourcePermission.resource_type == resource_type,
    ]

    if is_privileged:
        # Admin/owner: all resources in workspace for this service/type
        stmt = select(ResourcePermission.resource_id).where(*base_filter).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all()), True

    # Non-privileged: UNION of all access paths
    # 1. Resources owned by user
    owned = select(ResourcePermission.resource_id).where(
        *base_filter,
        ResourcePermission.owner_id == user_id,
    )

    queries = [owned]

    # 2. Workspace-visible resources
    if action == "view":
        ws_visible = select(ResourcePermission.resource_id).where(
            *base_filter,
            ResourcePermission.visibility == "workspace",
        )
        queries.append(ws_visible)
    elif action == "edit" and workspace_role == "editor":
        ws_editable = select(ResourcePermission.resource_id).where(
            *base_filter,
            ResourcePermission.visibility == "workspace",
        )
        queries.append(ws_editable)

    # 3. Direct user shares
    if action == "view":
        user_shared = (
            select(ResourcePermission.resource_id)
            .join(
                ResourceShare,
                ResourceShare.resource_permission_id == ResourcePermission.id,
            )
            .where(
                *base_filter,
                ResourceShare.grantee_type == "user",
                ResourceShare.grantee_id == user_id,
            )
        )
    else:
        user_shared = (
            select(ResourcePermission.resource_id)
            .join(
                ResourceShare,
                ResourceShare.resource_permission_id == ResourcePermission.id,
            )
            .where(
                *base_filter,
                ResourceShare.grantee_type == "user",
                ResourceShare.grantee_id == user_id,
                ResourceShare.permission == "edit",
            )
        )
    queries.append(user_shared)

    # 4. Group shares
    if group_ids:
        if action == "view":
            group_shared = (
                select(ResourcePermission.resource_id)
                .join(
                    ResourceShare,
                    ResourceShare.resource_permission_id == ResourcePermission.id,
                )
                .where(
                    *base_filter,
                    ResourceShare.grantee_type == "group",
                    ResourceShare.grantee_id.in_(group_ids),
                )
            )
        else:
            group_shared = (
                select(ResourcePermission.resource_id)
                .join(
                    ResourceShare,
                    ResourceShare.resource_permission_id == ResourcePermission.id,
                )
                .where(
                    *base_filter,
                    ResourceShare.grantee_type == "group",
                    ResourceShare.grantee_id.in_(group_ids),
                    ResourceShare.permission == "edit",
                )
            )
        queries.append(group_shared)

    combined = union(*queries)
    stmt = select(combined.c.resource_id)
    if limit is not None:
        stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all()), False
