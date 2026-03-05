import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.group import Group, GroupMembership
from src.models.user import User


async def create_group(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    name: str,
    created_by: uuid.UUID,
    description: str | None = None,
) -> Group:
    group = Group(
        workspace_id=workspace_id,
        name=name,
        description=description,
        created_by=created_by,
    )
    db.add(group)
    await db.commit()
    return group


async def list_groups(db: AsyncSession, workspace_id: uuid.UUID) -> list[Group]:
    stmt = (
        select(Group)
        .where(Group.workspace_id == workspace_id)
        .order_by(Group.created_at)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_group(
    db: AsyncSession,
    group_id: uuid.UUID,
    name: str | None = None,
    description: str | None = None,
) -> Group:
    group = await db.get(Group, group_id)
    if not group:
        raise ValueError("Group not found")
    if name is not None:
        group.name = name
    if description is not None:
        group.description = description
    await db.commit()
    return group


async def delete_group(db: AsyncSession, group_id: uuid.UUID) -> None:
    group = await db.get(Group, group_id)
    if not group:
        raise ValueError("Group not found")
    await db.delete(group)
    await db.commit()


async def add_member(
    db: AsyncSession, group_id: uuid.UUID, user_id: uuid.UUID
) -> GroupMembership:
    membership = GroupMembership(group_id=group_id, user_id=user_id)
    db.add(membership)
    await db.commit()
    return membership


async def remove_member(
    db: AsyncSession, group_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    stmt = select(GroupMembership).where(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == user_id,
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    if not membership:
        raise ValueError("Group membership not found")
    await db.delete(membership)
    await db.commit()


async def list_group_members(db: AsyncSession, group_id: uuid.UUID) -> list[dict]:
    stmt = (
        select(GroupMembership, User)
        .join(User, GroupMembership.user_id == User.id)
        .where(GroupMembership.group_id == group_id)
        .order_by(GroupMembership.added_at)
    )
    result = await db.execute(stmt)
    return [
        {
            "user_id": membership.user_id,
            "email": user.email,
            "name": user.name,
            "added_at": membership.added_at,
        }
        for membership, user in result.all()
    ]
