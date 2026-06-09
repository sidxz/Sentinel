import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt import (
    _AUD_ACCESS,
    _AUD_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from src.config import settings
from src.schemas.validators import sanitize_url, strip_html
from src.models.group import GroupMembership
from src.models.user import SocialAccount, User
from src.models.workspace import WorkspaceMembership
from src.services import token_service


class CrossProviderEmailConflict(Exception):
    """Raised when an IdP login's email matches a user from a different provider."""


def is_email_verified_claim(userinfo: dict) -> bool:
    """Strictly check that an OIDC ``email_verified`` claim is the boolean True.

    Per OIDC Core 1.0 §5.1, ``email_verified`` is a boolean. Some IdPs emit
    stringified booleans (``"true"``/``"false"``); the string ``"false"`` is
    truthy in Python and would bypass a naive ``not userinfo.get(...)`` check,
    letting an attacker sign in with a claimed-but-unverified email. Strictly
    compare against ``True`` so any non-boolean value fails closed.
    """
    return userinfo.get("email_verified") is True


async def find_or_create_user(
    db: AsyncSession,
    provider: str,
    provider_user_id: str,
    email: str,
    name: str,
    organization_id: uuid.UUID,
    avatar_url: str | None = None,
    provider_data: dict | None = None,
) -> User:
    """Find existing user by social account or create a new one."""
    avatar_url = sanitize_url(avatar_url)
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
        user.organization_id = organization_id
        if avatar_url:
            user.avatar_url = avatar_url
        social_account.provider_data = provider_data
        await db.commit()
        return user

    # Security: never auto-link across providers by email. Two different IdPs
    # reporting the same email are not necessarily the same human — especially
    # when one IdP has weaker verification than the other. Identity is keyed on
    # (provider, provider_user_id) only.
    stmt = select(User).where(User.email == email)
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing is not None:
        # Does this user already have ANY social account? If so, they signed up
        # via a different provider — a genuine cross-provider collision; reject
        # so a support flow (or future explicit link UI) handles it intentionally.
        sa_stmt = select(SocialAccount.id).where(SocialAccount.user_id == existing.id)
        has_social = (await db.execute(sa_stmt)).scalar_one_or_none() is not None
        if has_social:
            raise CrossProviderEmailConflict(
                f"An account with email {email!r} exists under a different identity "
                "provider. Sign in with the original provider, or contact an "
                "administrator to link the accounts."
            )

        # No social account = an admin-pre-provisioned (e.g. CSV-imported) bare
        # account. Link this provider to it so the user can sign in, instead of
        # locking them out of an account created for exactly this purpose.
        existing.name = strip_html(name)
        existing.organization_id = organization_id
        if avatar_url:
            existing.avatar_url = avatar_url
        db.add(
            SocialAccount(
                user_id=existing.id,
                provider=provider,
                provider_user_id=provider_user_id,
                provider_data=provider_data,
            )
        )
        if existing.email in settings.admin_email_list and not existing.is_admin:
            existing.is_admin = True
        await db.commit()
        return existing

    user = User(
        email=email,
        name=strip_html(name),
        avatar_url=avatar_url,
        organization_id=organization_id,
    )
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
    client_app_id: uuid.UUID | None = None,
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
    # family_id is generated inside create_refresh_token and embedded in the JWT
    refresh_token = create_refresh_token(user_id=user.id)

    # Store refresh token in Redis for rotation tracking. access_jti is bound
    # to the refresh record so revoke_token_family can blacklist the paired
    # access token on reuse detection — without this, the access token remains
    # valid for the remainder of its TTL after a theft signal fires.
    rt_payload = decode_token(refresh_token, audience=_AUD_REFRESH)
    at_payload = decode_token(access_token, audience=_AUD_ACCESS)
    family_id = rt_payload["fid"]
    await token_service.store_refresh_token(
        jti=rt_payload["jti"],
        user_id=user.id,
        family_id=family_id,
        workspace_id=workspace_id,
        client_app_id=client_app_id,
        access_jti=at_payload["jti"],
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
        payload = decode_token(refresh_token_str, audience=_AUD_REFRESH)
    except Exception:
        raise ValueError("Invalid refresh token")

    jti = payload["jti"]
    result = await token_service.consume_refresh_token(jti)

    if result is None:
        # Already consumed or expired — possible theft.
        # Extract family_id from the JWT and revoke the entire family.
        family_id = payload.get("fid")
        if family_id:
            await token_service.revoke_token_family(family_id)
        raise ValueError("Refresh token already used or expired")

    user_id, family_id, workspace_id, client_app_id = result
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        await token_service.revoke_token_family(family_id)
        raise ValueError("User not found or inactive")

    # Verify user still belongs to the original workspace
    stmt = select(WorkspaceMembership).where(
        WorkspaceMembership.user_id == user_id,
        WorkspaceMembership.workspace_id == workspace_id,
    )
    db_result = await db.execute(stmt)
    membership = db_result.scalar_one_or_none()
    if not membership:
        await token_service.revoke_token_family(family_id)
        raise ValueError("User is no longer a member of this workspace")

    # Get workspace slug
    from src.models.workspace import Workspace

    workspace = await db.get(Workspace, workspace_id)

    # Get group IDs
    stmt = (
        select(GroupMembership.group_id)
        .join(GroupMembership.group)
        .where(
            GroupMembership.user_id == user.id,
            GroupMembership.group.has(workspace_id=workspace_id),
        )
    )
    db_result = await db.execute(stmt)
    group_ids = [row[0] for row in db_result.all()]

    # Issue new tokens
    new_access = create_access_token(
        user_id=user.id,
        email=user.email,
        name=user.name,
        workspace_id=workspace_id,
        workspace_slug=workspace.slug,
        workspace_role=membership.role,
        groups=group_ids,
    )
    new_refresh = create_refresh_token(user_id=user.id, family_id=family_id)

    # Store new refresh token in same family, binding paired access jti so
    # family revocation can blacklist it.
    new_rt_payload = decode_token(new_refresh, audience=_AUD_REFRESH)
    new_at_payload = decode_token(new_access, audience=_AUD_ACCESS)
    await token_service.store_refresh_token(
        jti=new_rt_payload["jti"],
        user_id=user.id,
        family_id=family_id,
        workspace_id=workspace_id,
        client_app_id=client_app_id,
        access_jti=new_at_payload["jti"],
    )

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }
