import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.role import Role, RoleAction, ServiceAction, UserRole
from src.models.user import User


async def register_actions(
    db: AsyncSession,
    service_name: str,
    actions: list[dict],
) -> list[ServiceAction]:
    action_names = [a["action"] for a in actions]
    stmt = select(ServiceAction).where(
        ServiceAction.service_name == service_name,
        ServiceAction.action.in_(action_names),
    )
    result = await db.execute(stmt)
    existing = {sa.action: sa for sa in result.scalars().all()}

    # Update descriptions for existing actions
    for a in actions:
        if a["action"] in existing:
            sa = existing[a["action"]]
            if a.get("description") is not None:
                sa.description = a["description"]

    # Insert new actions
    new_actions = []
    for a in actions:
        if a["action"] not in existing:
            sa = ServiceAction(
                service_name=service_name,
                action=a["action"],
                description=a.get("description"),
            )
            db.add(sa)
            new_actions.append(sa)

    await db.commit()
    return list(existing.values()) + new_actions


async def check_action(
    db: AsyncSession,
    user_id: uuid.UUID,
    service_name: str,
    action: str,
    workspace_id: uuid.UUID,
) -> tuple[bool, list[str]]:
    stmt = (
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .join(RoleAction, RoleAction.role_id == Role.id)
        .join(ServiceAction, RoleAction.service_action_id == ServiceAction.id)
        .where(
            UserRole.user_id == user_id,
            Role.workspace_id == workspace_id,
            ServiceAction.service_name == service_name,
            ServiceAction.action == action,
        )
    )
    result = await db.execute(stmt)
    roles = list(result.scalars().all())
    return (len(roles) > 0, roles)


async def get_user_actions(
    db: AsyncSession,
    user_id: uuid.UUID,
    service_name: str,
    workspace_id: uuid.UUID,
) -> list[str]:
    stmt = (
        select(ServiceAction.action)
        .join(RoleAction, RoleAction.service_action_id == ServiceAction.id)
        .join(Role, RoleAction.role_id == Role.id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user_id,
            Role.workspace_id == workspace_id,
            ServiceAction.service_name == service_name,
        )
        .distinct()
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_service_actions(
    db: AsyncSession,
    service_name: str | None = None,
) -> list[ServiceAction]:
    stmt = select(ServiceAction).order_by(
        ServiceAction.service_name, ServiceAction.action
    )
    if service_name:
        stmt = stmt.where(ServiceAction.service_name == service_name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_service_action(
    db: AsyncSession,
    service_action_id: uuid.UUID,
) -> bool:
    action = await db.get(ServiceAction, service_action_id)
    if not action:
        return False
    await db.delete(action)
    await db.flush()
    return True


async def create_role(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    name: str,
    description: str | None = None,
    created_by: uuid.UUID | None = None,
) -> Role:
    role = Role(
        workspace_id=workspace_id,
        name=name,
        description=description,
        created_by=created_by,
    )
    db.add(role)
    await db.commit()
    return role


async def update_role(
    db: AsyncSession,
    role_id: uuid.UUID,
    name: str | None = None,
    description: str | None = None,
) -> Role:
    role = await db.get(Role, role_id)
    if not role:
        raise ValueError("Role not found")
    if name is not None:
        role.name = name
    if description is not None:
        role.description = description
    await db.commit()
    return role


async def delete_role(db: AsyncSession, role_id: uuid.UUID) -> None:
    role = await db.get(Role, role_id)
    if not role:
        raise ValueError("Role not found")
    await db.delete(role)
    await db.commit()


async def list_workspace_roles(
    db: AsyncSession,
    workspace_id: uuid.UUID,
) -> list[dict]:
    action_count = (
        select(func.count(RoleAction.id))
        .where(RoleAction.role_id == Role.id)
        .correlate(Role)
        .scalar_subquery()
    )
    member_count = (
        select(func.count(UserRole.id))
        .where(UserRole.role_id == Role.id)
        .correlate(Role)
        .scalar_subquery()
    )
    stmt = (
        select(
            Role, action_count.label("action_count"), member_count.label("member_count")
        )
        .where(Role.workspace_id == workspace_id)
        .order_by(Role.created_at)
    )
    result = await db.execute(stmt)
    return [
        {
            "id": role.id,
            "workspace_id": role.workspace_id,
            "name": role.name,
            "description": role.description,
            "created_by": role.created_by,
            "created_at": role.created_at,
            "action_count": ac,
            "member_count": mc,
        }
        for role, ac, mc in result.all()
    ]


async def add_role_actions(
    db: AsyncSession,
    role_id: uuid.UUID,
    service_action_ids: list[uuid.UUID],
) -> None:
    role = await db.get(Role, role_id)
    if not role:
        raise ValueError("Role not found")
    for said in service_action_ids:
        ra = RoleAction(role_id=role_id, service_action_id=said)
        db.add(ra)
    await db.commit()


async def remove_role_action(
    db: AsyncSession,
    role_id: uuid.UUID,
    service_action_id: uuid.UUID,
) -> None:
    stmt = select(RoleAction).where(
        RoleAction.role_id == role_id,
        RoleAction.service_action_id == service_action_id,
    )
    result = await db.execute(stmt)
    ra = result.scalar_one_or_none()
    if not ra:
        raise ValueError("Role action not found")
    await db.delete(ra)
    await db.commit()


async def list_role_actions(
    db: AsyncSession,
    role_id: uuid.UUID,
) -> list[ServiceAction]:
    stmt = (
        select(ServiceAction)
        .join(RoleAction, RoleAction.service_action_id == ServiceAction.id)
        .where(RoleAction.role_id == role_id)
        .order_by(ServiceAction.service_name, ServiceAction.action)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def assign_user_role(
    db: AsyncSession,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    assigned_by: uuid.UUID | None = None,
) -> UserRole:
    ur = UserRole(user_id=user_id, role_id=role_id, assigned_by=assigned_by)
    db.add(ur)
    await db.commit()
    return ur


async def remove_user_role(
    db: AsyncSession,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
) -> None:
    stmt = select(UserRole).where(
        UserRole.user_id == user_id,
        UserRole.role_id == role_id,
    )
    result = await db.execute(stmt)
    ur = result.scalar_one_or_none()
    if not ur:
        raise ValueError("User role not found")
    await db.delete(ur)
    await db.commit()


async def list_role_members(
    db: AsyncSession,
    role_id: uuid.UUID,
) -> list[dict]:
    stmt = (
        select(UserRole, User)
        .join(User, UserRole.user_id == User.id)
        .where(UserRole.role_id == role_id)
        .order_by(UserRole.assigned_at)
    )
    result = await db.execute(stmt)
    return [
        {
            "user_id": ur.user_id,
            "email": user.email,
            "name": user.name,
            "assigned_at": ur.assigned_at,
            "assigned_by": ur.assigned_by,
        }
        for ur, user in result.all()
    ]
