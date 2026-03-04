import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt import create_access_token, create_admin_token, create_refresh_token
from src.config import settings
from src.models.group import GroupMembership
from src.models.user import SocialAccount, User
from src.models.workspace import WorkspaceMembership


async def find_or_create_user(
    db: AsyncSession,
    provider: str,
    provider_user_id: str,
    email: str,
    name: str,
    avatar_url: str | None = None,
    provider_data: dict | None = None,
) -> User:
    """Find existing user by social account or create a new one."""
    # Check if social account exists
    stmt = select(SocialAccount).where(
        SocialAccount.provider == provider,
        SocialAccount.provider_user_id == provider_user_id,
    )
    result = await db.execute(stmt)
    social_account = result.scalar_one_or_none()

    if social_account:
        user = await db.get(User, social_account.user_id)
        # Update profile from provider
        user.name = name
        if avatar_url:
            user.avatar_url = avatar_url
        social_account.provider_data = provider_data
        await db.commit()
        return user

    # Check if user exists by email (link account)
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        user = User(email=email, name=name, avatar_url=avatar_url)
        db.add(user)
        await db.flush()

    social_account = SocialAccount(
        user_id=user.id,
        provider=provider,
        provider_user_id=provider_user_id,
        provider_data=provider_data,
    )
    db.add(social_account)

    # Auto-promote admin emails from config
    if user.email in settings.admin_email_list and not user.is_admin:
        user.is_admin = True

    await db.commit()
    return user


async def issue_tokens(
    db: AsyncSession,
    user: User,
    workspace_id: uuid.UUID,
    workspace_slug: str,
) -> dict[str, str]:
    """Issue access + refresh tokens for a user in a workspace context."""
    # Get workspace role
    stmt = select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.user_id == user.id,
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    if not membership:
        raise ValueError("User is not a member of this workspace")

    # Get group IDs
    stmt = (
        select(GroupMembership.group_id)
        .join(GroupMembership.group)
        .where(
            GroupMembership.user_id == user.id,
            GroupMembership.group.has(workspace_id=workspace_id),
        )
    )
    result = await db.execute(stmt)
    group_ids = [row[0] for row in result.all()]

    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        name=user.name,
        workspace_id=workspace_id,
        workspace_slug=workspace_slug,
        workspace_role=membership.role,
        groups=group_ids,
    )
    refresh_token = create_refresh_token(user_id=user.id)

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
