import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.workspace import Workspace, WorkspaceMembership
from src.services import token_service


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
    actor_role: str = "admin",
) -> WorkspaceMembership:
    # Only owners can grant the owner role
    if role == "owner" and actor_role != "owner":
        raise ValueError("Only workspace owners can grant the owner role")

    user = await db.execute(select(User).where(User.email == email))
    user = user.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    membership = WorkspaceMembership(
        workspace_id=workspace_id, user_id=user.id, role=role
    )
    db.add(membership)
    await db.commit()
    return membership


async def _count_owners(db: AsyncSession, workspace_id: uuid.UUID) -> int:
    # FOR UPDATE locks owner rows to prevent concurrent demotion/removal races
    stmt = (
        select(func.count())
        .where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.role == "owner",
        )
        .with_for_update()
    )
    result = await db.execute(stmt)
    return result.scalar_one()


async def update_member_role(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
    actor_role: str = "admin",
) -> WorkspaceMembership:
    stmt = (
        select(WorkspaceMembership)
        .where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
        .with_for_update()
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    if not membership:
        raise ValueError("Membership not found")

    # Only owners can grant the owner role
    if role == "owner" and actor_role != "owner":
        raise ValueError("Only workspace owners can grant the owner role")

    # Prevent demoting the last owner
    if membership.role == "owner" and role != "owner":
        if await _count_owners(db, workspace_id) <= 1:
            raise ValueError("Cannot demote the last workspace owner")

    # Only owners can demote other owners
    if membership.role == "owner" and actor_role != "owner":
        raise ValueError("Only workspace owners can change another owner's role")

    old_role = membership.role
    membership.role = role
    await db.commit()
    # Revoke tokens so stale role claims can't be used
    if role != old_role:
        await token_service.revoke_all_user_tokens(str(user_id))
    return membership


async def remove_member(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    actor_role: str = "admin",
) -> None:
    stmt = (
        select(WorkspaceMembership)
        .where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
        .with_for_update()
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    if not membership:
        raise ValueError("Membership not found")

    # Prevent removing an owner unless actor is also an owner
    if membership.role == "owner" and actor_role != "owner":
        raise ValueError("Only workspace owners can remove another owner")

    # Prevent removing the last owner
    if membership.role == "owner":
        if await _count_owners(db, workspace_id) <= 1:
            raise ValueError("Cannot remove the last workspace owner")

    await db.delete(membership)
    await db.commit()
    # Revoke tokens — user no longer belongs to this workspace
    await token_service.revoke_all_user_tokens(str(user_id))
