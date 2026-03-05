import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.workspace import Workspace, WorkspaceMembership


async def create_workspace(
    db: AsyncSession,
    name: str,
    slug: str,
    created_by: uuid.UUID,
    description: str | None = None,
) -> Workspace:
    workspace = Workspace(
        name=name, slug=slug, description=description, created_by=created_by
    )
    db.add(workspace)
    await db.flush()

    # Creator becomes owner
    membership = WorkspaceMembership(
        workspace_id=workspace.id, user_id=created_by, role="owner"
    )
    db.add(membership)
    await db.commit()
    return workspace


async def list_user_workspaces(db: AsyncSession, user_id: uuid.UUID) -> list[Workspace]:
    stmt = (
        select(Workspace)
        .join(WorkspaceMembership)
        .where(WorkspaceMembership.user_id == user_id)
        .order_by(Workspace.created_at)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_workspace(db: AsyncSession, workspace_id: uuid.UUID) -> Workspace | None:
    return await db.get(Workspace, workspace_id)


async def update_workspace(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    name: str | None = None,
    description: str | None = None,
) -> Workspace:
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise ValueError("Workspace not found")
    if name is not None:
        workspace.name = name
    if description is not None:
        workspace.description = description
    await db.commit()
    return workspace


async def delete_workspace(db: AsyncSession, workspace_id: uuid.UUID) -> None:
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise ValueError("Workspace not found")
    await db.delete(workspace)
    await db.commit()


async def list_members(db: AsyncSession, workspace_id: uuid.UUID) -> list[dict]:
    stmt = (
        select(WorkspaceMembership, User)
        .join(User, WorkspaceMembership.user_id == User.id)
        .where(WorkspaceMembership.workspace_id == workspace_id)
        .order_by(WorkspaceMembership.joined_at)
    )
    result = await db.execute(stmt)
    return [
        {
            "user_id": membership.user_id,
            "email": user.email,
            "name": user.name,
            "avatar_url": user.avatar_url,
            "role": membership.role,
            "joined_at": membership.joined_at,
        }
        for membership, user in result.all()
    ]


async def invite_member(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    email: str,
    role: str = "viewer",
) -> WorkspaceMembership:
    user = await db.execute(select(User).where(User.email == email))
    user = user.scalar_one_or_none()
    if not user:
        raise ValueError(f"User with email {email} not found")

    membership = WorkspaceMembership(
        workspace_id=workspace_id, user_id=user.id, role=role
    )
    db.add(membership)
    await db.commit()
    return membership


async def update_member_role(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
) -> WorkspaceMembership:
    stmt = select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.user_id == user_id,
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    if not membership:
        raise ValueError("Membership not found")
    membership.role = role
    await db.commit()
    return membership


async def remove_member(
    db: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    stmt = select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.user_id == user_id,
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    if not membership:
        raise ValueError("Membership not found")
    await db.delete(membership)
    await db.commit()
