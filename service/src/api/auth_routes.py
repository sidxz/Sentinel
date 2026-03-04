import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse, RedirectResponse

from src.api.dependencies import require_admin
from src.auth.jwt import create_admin_token
from src.auth.providers import get_configured_providers, oauth
from src.config import settings
from src.database import get_db
from src.schemas.auth import ProviderListResponse, RefreshRequest, TokenResponse
from src.services import auth_service

logger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/providers", response_model=ProviderListResponse)
async def list_providers():
    return ProviderListResponse(providers=get_configured_providers())


@router.get("/login/{provider}")
async def login(provider: str, request: Request):
    configured = get_configured_providers()
    if provider not in configured:
        raise HTTPException(status_code=400, detail=f"Provider '{provider}' is not configured")
    client = oauth.create_client(provider)
    redirect_uri = f"{settings.base_url}/auth/callback/{provider}"
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/callback/{provider}")
async def callback(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    configured = get_configured_providers()
    if provider not in configured:
        raise HTTPException(status_code=400, detail=f"Provider '{provider}' is not configured")

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

    # TODO: redirect to frontend with auth code / set cookie
    # For now, redirect to frontend with user ID for workspace selection
    return RedirectResponse(url=f"{settings.frontend_url}/auth/callback?user_id={user.id}")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest):
    # TODO: validate refresh token from Redis, issue new access token
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/logout")
async def logout():
    # TODO: revoke refresh token in Redis
    raise HTTPException(status_code=501, detail="Not implemented yet")


# --- Admin auth endpoints ---


@router.get("/admin/login/{provider}")
async def admin_login(provider: str, request: Request):
    configured = get_configured_providers()
    if provider not in configured:
        raise HTTPException(status_code=400, detail=f"Provider '{provider}' is not configured")
    client = oauth.create_client(provider)
    redirect_uri = f"{settings.base_url}/auth/admin/callback/{provider}"
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/admin/callback/{provider}")
async def admin_callback(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    import traceback

    try:
        configured = get_configured_providers()
        if provider not in configured:
            raise HTTPException(status_code=400, detail=f"Provider '{provider}' is not configured")

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

        admin_token = create_admin_token(user_id=user.id, email=user.email, name=user.name)
        response = RedirectResponse(url=f"{settings.admin_url}/", status_code=302)
        response.set_cookie(
            key="admin_token",
            value=admin_token,
            httponly=True,
            samesite="lax",
            max_age=8 * 3600,
            path="/",
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("admin callback error", error=str(e), traceback=tb)
        return JSONResponse(status_code=500, content={"detail": str(e), "traceback": tb})


@router.get("/admin/me")
async def admin_me(admin: dict = Depends(require_admin)):
    return {"id": admin["sub"], "email": admin["email"], "name": admin["name"]}


@router.post("/admin/logout")
async def admin_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie("admin_token", path="/")
    return response
