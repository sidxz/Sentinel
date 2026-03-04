import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.group import Group
from src.models.permission import ResourcePermission
from src.models.user import SocialAccount, User
from src.models.workspace import Workspace, WorkspaceMembership


async def get_stats(db: AsyncSession) -> dict:
    total_users = await db.scalar(select(func.count(User.id)))
    total_workspaces = await db.scalar(select(func.count(Workspace.id)))
    total_groups = await db.scalar(select(func.count(Group.id)))
    total_resources = await db.scalar(select(func.count(ResourcePermission.id)))

    recent_stmt = (
        select(User, func.count(WorkspaceMembership.id).label("workspace_count"))
        .outerjoin(WorkspaceMembership, User.id == WorkspaceMembership.user_id)
        .group_by(User.id)
        .order_by(User.created_at.desc())
        .limit(5)
    )
    result = await db.execute(recent_stmt)
    recent_users = [
        {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "avatar_url": user.avatar_url,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "workspace_count": count,
        }
        for user, count in result.all()
    ]

    return {
        "total_users": total_users or 0,
        "total_workspaces": total_workspaces or 0,
        "total_groups": total_groups or 0,
        "total_resources": total_resources or 0,
        "recent_users": recent_users,
    }


async def list_users(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
) -> dict:
    base_query = (
        select(User, func.count(WorkspaceMembership.id).label("workspace_count"))
        .outerjoin(WorkspaceMembership, User.id == WorkspaceMembership.user_id)
        .group_by(User.id)
    )

    if search:
        base_query = base_query.where(
            User.email.ilike(f"%{search}%") | User.name.ilike(f"%{search}%")
        )

    # Count total
    count_query = select(func.count()).select_from(User)
    if search:
        count_query = count_query.where(
            User.email.ilike(f"%{search}%") | User.name.ilike(f"%{search}%")
        )
    total = await db.scalar(count_query) or 0

    # Fetch page
    stmt = base_query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)

    items = [
        {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "avatar_url": user.avatar_url,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "workspace_count": count,
        }
        for user, count in result.all()
    ]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_user_detail(db: AsyncSession, user_id: uuid.UUID) -> dict | None:
    stmt = (
        select(User)
        .options(selectinload(User.social_accounts))
        .where(User.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        return None

    # Get memberships with workspace info
    membership_stmt = (
        select(WorkspaceMembership, Workspace)
        .join(Workspace, WorkspaceMembership.workspace_id == Workspace.id)
        .where(WorkspaceMembership.user_id == user_id)
        .order_by(WorkspaceMembership.joined_at)
    )
    membership_result = await db.execute(membership_stmt)

    memberships = [
        {
            "workspace_id": m.workspace_id,
            "workspace_name": w.name,
            "workspace_slug": w.slug,
            "role": m.role,
            "joined_at": m.joined_at,
        }
        for m, w in membership_result.all()
    ]

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "social_accounts": [
            {"id": sa.id, "provider": sa.provider, "provider_user_id": sa.provider_user_id}
            for sa in user.social_accounts
        ],
        "memberships": memberships,
    }


async def update_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str | None = None,
    is_active: bool | None = None,
) -> User | None:
    user = await db.get(User, user_id)
    if not user:
        return None
    if name is not None:
        user.name = name
    if is_active is not None:
        user.is_active = is_active
    await db.commit()
    return user


async def list_workspaces(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
) -> dict:
    base_query = (
        select(Workspace, func.count(WorkspaceMembership.id).label("member_count"))
        .outerjoin(WorkspaceMembership, Workspace.id == WorkspaceMembership.workspace_id)
        .group_by(Workspace.id)
    )

    if search:
        base_query = base_query.where(
            Workspace.name.ilike(f"%{search}%") | Workspace.slug.ilike(f"%{search}%")
        )

    count_query = select(func.count()).select_from(Workspace)
    if search:
        count_query = count_query.where(
            Workspace.name.ilike(f"%{search}%") | Workspace.slug.ilike(f"%{search}%")
        )
    total = await db.scalar(count_query) or 0

    stmt = base_query.order_by(Workspace.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)

    items = [
        {
            "id": ws.id,
            "slug": ws.slug,
            "name": ws.name,
            "description": ws.description,
            "created_by": ws.created_by,
            "created_at": ws.created_at,
            "member_count": count,
        }
        for ws, count in result.all()
    ]

    return {"items": items, "total": total, "page": page, "page_size": page_size}
