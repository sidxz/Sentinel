import html
import uuid
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from src.api.dependencies import CurrentUser, get_current_user, require_admin
from src.auth.jwt import create_admin_token, decode_token
from src.auth.providers import get_configured_providers, oauth
from src.config import settings
from src.database import get_db
from src.models.client_app import ClientApp
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
    auth_code_service,
    auth_service,
    token_service,
    workspace_service,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["auth"])


def _error_page(status_code: int, title: str, message: str) -> HTMLResponse:
    # Base64-encoded splash.png is too large — use an inline SVG shield instead.
    # The response overrides the global CSP to allow inline styles and the SVG.
    safe_title = html.escape(title)
    safe_message = html.escape(message)
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title} — Sentinel Auth</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ min-height: 100vh; display: flex; align-items: center; justify-content: center;
         background: #09090b; color: #e4e4e7; font-family: system-ui, -apple-system, sans-serif; }}
  .card {{ max-width: 420px; width: 100%; border: 1px solid #27272a;
           border-radius: 0.75rem; background: #18181b; overflow: hidden; }}
  .header {{ background: #f43737; padding: 1.5rem; text-align: center; }}
  .shield {{ width: 40px; height: 40px; margin: 0 auto 0.5rem; }}
  .brand {{ font-size: 0.625rem; font-weight: 700; letter-spacing: 0.15em;
            text-transform: uppercase; color: rgba(255,255,255,0.85); }}
  .body {{ padding: 2rem 2rem 1.75rem; text-align: center; }}
  h1 {{ font-size: 1.125rem; font-weight: 600; margin-bottom: 0.75rem; }}
  p {{ font-size: 0.875rem; color: #a1a1aa; line-height: 1.6; }}
  .meta {{ font-size: 0.75rem; color: #3f3f46; margin-top: 1.5rem;
           padding-top: 1rem; border-top: 1px solid #27272a; }}
</style>
</head>
<body>
  <div class="card">
    <div class="header">
      <svg class="shield" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.25C17.25 22.15 21 17.25 21 12V7l-9-5z"
              fill="rgba(0,0,0,0.2)" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>
        <rect x="10" y="9" width="4" height="5" rx="0.5" fill="white" opacity="0.9"/>
        <circle cx="12" cy="8.5" r="2" fill="none" stroke="white" stroke-width="1.5" opacity="0.9"/>
      </svg>
      <div class="brand">Sentinel Auth</div>
    </div>
    <div class="body">
      <h1>{safe_title}</h1>
      <p>{safe_message}</p>
      <div class="meta">Error {status_code}</div>
    </div>
  </div>
</body>
</html>"""
    resp = HTMLResponse(content=page, status_code=status_code)
    resp.headers["X-CSP-Override"] = "html-page"
    return resp


@router.get("/providers", response_model=ProviderListResponse)
async def list_providers():
    return ProviderListResponse(providers=get_configured_providers())


@router.get("/login/{provider}")
@limiter.limit("10/minute")
async def login(
    provider: str,
    request: Request,
    redirect_uri: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    configured = get_configured_providers()
    if provider not in configured:
        return _error_page(
            400,
            "Provider Not Available",
            f"The login provider \u201c{provider}\u201d is not configured on this server.",
        )

    # Validate redirect_uri against any active allowed app
    stmt = select(ClientApp).where(
        ClientApp.is_active.is_(True),
        ClientApp.redirect_uris.any(redirect_uri),
    )
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        return _error_page(
            400,
            "App Not Allowed",
            "The redirect URI is not registered for any active app. Check that the app is registered and enabled in the admin panel.",
        )

    # Store in session for callback
    request.session["redirect_uri"] = redirect_uri

    client = oauth.create_client(provider)
    oauth_redirect_uri = f"{settings.base_url}/auth/callback/{provider}"
    return await client.authorize_redirect(request, oauth_redirect_uri)


@router.get("/callback/{provider}")
@limiter.limit("10/minute")
async def callback(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        configured = get_configured_providers()
        if provider not in configured:
            return _error_page(
                400,
                "Provider Not Available",
                f"The login provider \u201c{provider}\u201d is not configured on this server.",
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
                primary = next(
                    (e for e in emails if e.get("primary") and e.get("verified")),
                    None,
                )
                if not primary:
                    return _error_page(
                        403,
                        "Email Not Verified",
                        "Your GitHub account does not have a verified primary email. "
                        "Please verify your email on GitHub and try again.",
                    )
                profile["email"] = primary["email"]
            provider_user_id = str(profile["id"])
            email = profile["email"]
            name = profile.get("name") or profile.get("login", "")
            avatar_url = profile.get("avatar_url")
        else:
            # OIDC providers (Google, EntraID) — parse ID token
            userinfo = token.get("userinfo", {})
            if not userinfo.get("email_verified", False):
                return _error_page(
                    403,
                    "Email Not Verified",
                    "Your identity provider did not confirm your email address. "
                    "Please verify your email and try again.",
                )
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

        # Retrieve redirect_uri from session and clear it
        redirect_uri = request.session.pop("redirect_uri", None)
        request.session.clear()
        if not redirect_uri:
            return _error_page(
                400,
                "Session Expired",
                "Your login session has expired. Please go back and try again.",
            )

        # Re-validate redirect_uri still belongs to an active allowed app
        stmt = select(ClientApp).where(
            ClientApp.is_active.is_(True),
            ClientApp.redirect_uris.any(redirect_uri),
        )
        result = await db.execute(stmt)
        client_app = result.scalar_one_or_none()
        if not client_app:
            return _error_page(
                400,
                "App Not Allowed",
                "The app you are trying to sign into has been disabled. Contact your administrator.",
            )

        # Generate auth code and redirect
        code = await auth_code_service.create_auth_code(
            user.id, client_app_id=client_app.id
        )
        separator = "&" if "?" in redirect_uri else "?"
        return RedirectResponse(
            url=f"{redirect_uri}{separator}{urlencode({'code': code})}"
        )
    except Exception as e:
        logger.error("auth callback error", error=str(e), exc_info=True)
        return _error_page(
            500,
            "Authentication Failed",
            "Something went wrong during sign-in. Please try again.",
        )


@router.get("/workspaces", response_model=list[WorkspaceOptionResponse])
@limiter.limit("10/minute")
async def list_workspaces_for_login(
    request: Request,
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """List workspaces a user belongs to (for workspace selection after OAuth)."""
    code_data = await auth_code_service.peek_auth_code(code)
    if not code_data:
        raise HTTPException(
            status_code=400, detail="Invalid or expired authorization code"
        )

    user_id = uuid.UUID(code_data["user_id"])
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
    """Exchange authorization code + workspace_id for JWT tokens."""
    code_data = await auth_code_service.consume_auth_code(body.code)
    if not code_data:
        raise HTTPException(
            status_code=400, detail="Invalid or expired authorization code"
        )

    user_id = uuid.UUID(code_data["user_id"])
    client_app_id = (
        uuid.UUID(code_data["client_app_id"])
        if code_data.get("client_app_id")
        else None
    )
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    workspace = await db.get(Workspace, body.workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    try:
        tokens = await auth_service.issue_tokens(
            db, user, workspace.id, workspace.slug, client_app_id=client_app_id
        )
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
        payload = decode_token(token_str, audience="sentinel:access")
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
                primary = next(
                    (e for e in emails if e.get("primary") and e.get("verified")),
                    None,
                )
                if not primary:
                    return RedirectResponse(
                        url=f"{settings.admin_url}/login?error=email_not_verified",
                        status_code=302,
                    )
                profile["email"] = primary["email"]
            provider_user_id = str(profile["id"])
            email = profile["email"]
            name = profile.get("name") or profile.get("login", "")
            avatar_url = profile.get("avatar_url")
        else:
            userinfo = token.get("userinfo", {})
            if not userinfo.get("email_verified", False):
                return RedirectResponse(
                    url=f"{settings.admin_url}/login?error=email_not_verified",
                    status_code=302,
                )
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
