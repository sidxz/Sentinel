import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt import create_access_token, create_refresh_token, decode_token
from src.config import settings
from src.schemas.validators import strip_html
from src.models.group import GroupMembership
from src.models.user import SocialAccount, User
from src.models.workspace import WorkspaceMembership
from src.services import token_service


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
        # Update profile from provider (sanitize IdP data)
        user.name = strip_html(name)
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
        user = User(email=email, name=strip_html(name), avatar_url=avatar_url)
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

    # Store refresh token in Redis for rotation tracking
    rt_payload = decode_token(refresh_token)
    family_id = str(uuid.uuid4())
    await token_service.store_refresh_token(
        jti=rt_payload["jti"],
        user_id=user.id,
        family_id=family_id,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


async def rotate_refresh_token(
    db: AsyncSession,
    refresh_token_str: str,
) -> dict[str, str]:
    """Consume a refresh token and issue a new token pair.

    Implements refresh token rotation with reuse detection:
    - If the token is valid, consume it, issue new pair, same family.
    - If the token was already consumed, revoke the entire family (theft signal).
    """
    try:
        payload = decode_token(refresh_token_str)
    except Exception:
        raise ValueError("Invalid refresh token")

    if payload.get("type") != "refresh":
        raise ValueError("Invalid token type")

    jti = payload["jti"]
    result = await token_service.consume_refresh_token(jti)

    if result is None:
        # Already consumed or expired — possible theft. Try to find family via jti pattern.
        # Since we can't recover the family_id, this is a hard fail.
        raise ValueError("Refresh token already used or expired")

    user_id, family_id = result
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        await token_service.revoke_token_family(family_id)
        raise ValueError("User not found or inactive")

    # Find user's most recent workspace membership to re-issue tokens
    stmt = (
        select(WorkspaceMembership)
        .where(WorkspaceMembership.user_id == user_id)
        .order_by(WorkspaceMembership.id.desc())
        .limit(1)
    )
    db_result = await db.execute(stmt)
    membership = db_result.scalar_one_or_none()
    if not membership:
        await token_service.revoke_token_family(family_id)
        raise ValueError("User has no workspace membership")

    # Get workspace slug
    from src.models.workspace import Workspace

    workspace = await db.get(Workspace, membership.workspace_id)

    # Get group IDs
    stmt = (
        select(GroupMembership.group_id)
        .join(GroupMembership.group)
        .where(
            GroupMembership.user_id == user.id,
            GroupMembership.group.has(workspace_id=membership.workspace_id),
        )
    )
    db_result = await db.execute(stmt)
    group_ids = [row[0] for row in db_result.all()]

    # Issue new tokens
    new_access = create_access_token(
        user_id=user.id,
        email=user.email,
        name=user.name,
        workspace_id=membership.workspace_id,
        workspace_slug=workspace.slug,
        workspace_role=membership.role,
        groups=group_ids,
    )
    new_refresh = create_refresh_token(user_id=user.id)

    # Store new refresh token in same family
    new_rt_payload = decode_token(new_refresh)
    await token_service.store_refresh_token(
        jti=new_rt_payload["jti"],
        user_id=user.id,
        family_id=family_id,
    )

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }
