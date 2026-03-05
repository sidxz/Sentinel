import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse, RedirectResponse

from src.api.dependencies import CurrentUser, get_current_user, require_admin
from src.auth.jwt import create_admin_token, decode_token
from src.auth.providers import get_configured_providers, oauth
from src.config import settings
from src.database import get_db
from src.models.user import User
from src.models.workspace import Workspace, WorkspaceMembership
from src.schemas.auth import (
    ProviderListResponse,
    RefreshRequest,
    SelectWorkspaceRequest,
    TokenResponse,
    WorkspaceOptionResponse,
)
from src.middleware.rate_limit import limiter
from src.services import (
    activity_service,
    auth_service,
    token_service,
    workspace_service,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/providers", response_model=ProviderListResponse)
async def list_providers():
    return ProviderListResponse(providers=get_configured_providers())


@router.get("/login/{provider}")
@limiter.limit("10/minute")
async def login(provider: str, request: Request):
    configured = get_configured_providers()
    if provider not in configured:
        raise HTTPException(
            status_code=400, detail=f"Provider '{provider}' is not configured"
        )
    client = oauth.create_client(provider)
    redirect_uri = f"{settings.base_url}/auth/callback/{provider}"
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/callback/{provider}")
@limiter.limit("10/minute")
async def callback(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    configured = get_configured_providers()
    if provider not in configured:
        raise HTTPException(
            status_code=400, detail=f"Provider '{provider}' is not configured"
        )

    client = oauth.create_client(provider)
    token = await client.authorize_access_token(request)

    # Extract user info based on provider
    if provider == "github":
        resp = await client.get("user", token=token)
        profile = resp.json()
        # GitHub may not return email in profile, fetch from emails endpoint
        if not profile.get("email"):
            resp = await client.get("user/emails", token=token)
            emails = resp.json()
            primary = next((e for e in emails if e.get("primary")), emails[0])
            profile["email"] = primary["email"]
        provider_user_id = str(profile["id"])
        email = profile["email"]
        name = profile.get("name") or profile.get("login", "")
        avatar_url = profile.get("avatar_url")
    else:
        # OIDC providers (Google, EntraID) — parse ID token
        userinfo = token.get("userinfo", {})
        provider_user_id = userinfo.get("sub", "")
        email = userinfo.get("email", "")
        name = userinfo.get("name", "")
        avatar_url = userinfo.get("picture")
        profile = dict(userinfo)

    user = await auth_service.find_or_create_user(
        db=db,
        provider=provider,
        provider_user_id=provider_user_id,
        email=email,
        name=name,
        avatar_url=avatar_url,
        provider_data=profile,
    )

    await activity_service.log_activity(
        db,
        action="user_login",
        target_type="user",
        target_id=user.id,
        actor_id=user.id,
        detail={
            "provider": provider,
            "ip": request.client.host if request.client else None,
        },
    )
    await db.commit()

    # TODO: redirect to frontend with auth code / set cookie
    # For now, redirect to frontend with user ID for workspace selection
    return RedirectResponse(
        url=f"{settings.frontend_url}/auth/callback?user_id={user.id}"
    )


@router.get("/workspaces", response_model=list[WorkspaceOptionResponse])
@limiter.limit("10/minute")
async def list_workspaces_for_login(
    request: Request,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List workspaces a user belongs to (for workspace selection after OAuth)."""
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    workspaces = await workspace_service.list_user_workspaces(db, user_id)

    result = []
    for ws in workspaces:
        stmt = select(WorkspaceMembership.role).where(
            WorkspaceMembership.workspace_id == ws.id,
            WorkspaceMembership.user_id == user_id,
        )
        role_result = await db.execute(stmt)
        role = role_result.scalar_one()
        result.append(
            WorkspaceOptionResponse(id=ws.id, name=ws.name, slug=ws.slug, role=role)
        )
    return result


@router.post("/token", response_model=TokenResponse)
@limiter.limit("10/minute")
async def select_workspace_and_issue_tokens(
    request: Request,
    body: SelectWorkspaceRequest,
    db: AsyncSession = Depends(get_db),
):
    """Exchange user_id + workspace_id for JWT tokens after OAuth login."""
    user = await db.get(User, body.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    workspace = await db.get(Workspace, body.workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    try:
        tokens = await auth_service.issue_tokens(db, user, workspace.id, workspace.slug)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return tokens


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh_token(
    request: Request,
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        tokens = await auth_service.rotate_refresh_token(db, body.refresh_token)
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=str(e) if isinstance(e, ValueError) else "Invalid refresh token",
        )
    return tokens


@router.post("/logout")
async def logout(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    # Blacklist the current access token
    auth_header = request.headers.get("Authorization", "")
    token_str = auth_header.removeprefix("Bearer ")
    try:
        payload = decode_token(token_str)
        if jti := payload.get("jti"):
            await token_service.blacklist_access_token(jti, payload["exp"])
        # Revoke all refresh token families for this user
        await token_service.revoke_all_user_tokens(payload["sub"])
    except Exception:
        pass  # Token already expired or invalid — still log out
    return {"ok": True}


# --- Admin auth endpoints ---


@router.get("/admin/login/{provider}")
@limiter.limit("5/minute")
async def admin_login(provider: str, request: Request):
    configured = get_configured_providers()
    if provider not in configured:
        raise HTTPException(
            status_code=400, detail=f"Provider '{provider}' is not configured"
        )
    client = oauth.create_client(provider)
    redirect_uri = f"{settings.base_url}/auth/admin/callback/{provider}"
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/admin/callback/{provider}")
@limiter.limit("5/minute")
async def admin_callback(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        configured = get_configured_providers()
        if provider not in configured:
            raise HTTPException(
                status_code=400, detail=f"Provider '{provider}' is not configured"
            )

        client = oauth.create_client(provider)
        token = await client.authorize_access_token(request)

        if provider == "github":
            resp = await client.get("user", token=token)
            profile = resp.json()
            if not profile.get("email"):
                resp = await client.get("user/emails", token=token)
                emails = resp.json()
                primary = next((e for e in emails if e.get("primary")), emails[0])
                profile["email"] = primary["email"]
            provider_user_id = str(profile["id"])
            email = profile["email"]
            name = profile.get("name") or profile.get("login", "")
            avatar_url = profile.get("avatar_url")
        else:
            userinfo = token.get("userinfo", {})
            provider_user_id = userinfo.get("sub", "")
            email = userinfo.get("email", "")
            name = userinfo.get("name", "")
            avatar_url = userinfo.get("picture")
            profile = dict(userinfo)

        user = await auth_service.find_or_create_user(
            db=db,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
            provider_data=profile,
        )

        if not user.is_admin:
            return RedirectResponse(
                url=f"{settings.admin_url}/login?error=not_admin",
                status_code=302,
            )

        await activity_service.log_activity(
            db,
            action="admin_login",
            target_type="user",
            target_id=user.id,
            actor_id=user.id,
            detail={
                "provider": provider,
                "ip": request.client.host if request.client else None,
            },
        )
        await db.commit()

        admin_token = create_admin_token(
            user_id=user.id, email=user.email, name=user.name
        )
        response = RedirectResponse(url=f"{settings.admin_url}/", status_code=302)
        response.set_cookie(
            key="admin_token",
            value=admin_token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="strict",
            max_age=3600,
            path="/",
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error("admin callback error", error=str(e), exc_info=True)
        return JSONResponse(
            status_code=500, content={"detail": "Authentication failed"}
        )


@router.get("/admin/me")
async def admin_me(admin: dict = Depends(require_admin)):
    return {"id": admin["sub"], "email": admin["email"], "name": admin["name"]}


@router.post("/admin/logout")
async def admin_logout(request: Request, admin: dict = Depends(require_admin)):
    # Blacklist the admin token so it can't be replayed
    if jti := admin.get("jti"):
        await token_service.blacklist_access_token(jti, admin["exp"])
    response = JSONResponse({"ok": True})
    response.delete_cookie("admin_token", path="/")
    return response
