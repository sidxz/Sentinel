"""AuthZ Mode endpoints — IdP token validation + authorization JWT issuance."""

import uuid

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import ServiceKeyContext, require_service_context
from src.auth.jwt import create_authz_token
from src.config import settings
from src.database import get_db
from src.middleware.rate_limit import limiter
from src.models.workspace import Workspace, WorkspaceMembership
from src.schemas.authz import (
    AuthzResolveRequest,
    AuthzResolveResponse,
    AuthzUserResponse,
    AuthzWorkspaceOption,
    AuthzWorkspaceResponse,
)
from src.services import auth_service
from src.services.idp_validator import IdpValidationError, validate_idp_token
from src.services.role_service import get_user_actions

logger = structlog.get_logger()

router = APIRouter(prefix="/authz", tags=["authz"])


@router.get("/idp/{provider}/login")
@limiter.limit("10/minute")
async def idp_login(request: Request, provider: str, redirect_uri: str, nonce: str):
    """Redirect to an OAuth provider that requires server-side code exchange (e.g. GitHub).

    Stores redirect_uri and nonce in the session, then redirects to the
    provider's authorization URL. The callback endpoint exchanges the code
    and redirects back with the token in the URL hash.
    """
    if provider != "github":
        raise HTTPException(
            status_code=400, detail=f"Proxy login not supported for {provider}"
        )
    if not settings.github_client_id or not settings.github_client_secret:
        raise HTTPException(status_code=400, detail="GitHub OAuth is not configured")

    request.session["authz_idp_redirect_uri"] = redirect_uri
    request.session["authz_idp_nonce"] = nonce

    params = (
        f"client_id={settings.github_client_id}"
        f"&redirect_uri={settings.base_url}/authz/idp/github/callback"
        f"&scope=read:user user:email"
        f"&state={uuid.uuid4().hex}"
    )
    return RedirectResponse(
        url=f"https://github.com/login/oauth/authorize?{params}",
        status_code=302,
    )


@router.get("/idp/{provider}/callback")
@limiter.limit("10/minute")
async def idp_callback(request: Request, provider: str, code: str):
    """Exchange authorization code for access token and redirect back to the frontend.

    Exchanges GitHub's authorization code for an access token, then redirects
    to the stored redirect_uri with the access token in the URL hash as
    `id_token` (matching the implicit flow format the SDK expects).
    """
    if provider != "github":
        raise HTTPException(
            status_code=400, detail=f"Proxy callback not supported for {provider}"
        )

    redirect_uri = request.session.pop("authz_idp_redirect_uri", None)
    nonce = request.session.pop("authz_idp_nonce", None)
    if not redirect_uri:
        raise HTTPException(
            status_code=400,
            detail="No redirect_uri in session — start from /authz/idp/{provider}/login",
        )

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
    if resp.status_code != 200:
        logger.warning("github_code_exchange_failed", status=resp.status_code)
        raise HTTPException(status_code=502, detail="GitHub code exchange failed")

    token_data = resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        error = token_data.get("error_description", token_data.get("error", "unknown"))
        raise HTTPException(status_code=400, detail=f"GitHub OAuth error: {error}")

    # Redirect back with token in hash (matches SDK's handleCallback expectations)
    fragment = f"id_token={access_token}"
    if nonce:
        fragment += f"&nonce={nonce}"
    return RedirectResponse(url=f"{redirect_uri}#{fragment}", status_code=302)


@router.post("/resolve", response_model=AuthzResolveResponse)
@limiter.limit("10/minute")
async def resolve(
    request: Request,
    body: AuthzResolveRequest,
    service_ctx: ServiceKeyContext = Depends(require_service_context),
    db: AsyncSession = Depends(get_db),
):
    """Validate IdP token, provision user, and return authorization context.

    If workspace_id is provided, returns a signed authz JWT for that workspace.
    If omitted, returns the list of workspaces the user belongs to.
    """
    # 1. Validate IdP token against provider's JWKS
    try:
        idp_claims = await validate_idp_token(body.idp_token, body.provider)
    except IdpValidationError as e:
        logger.warning(
            "authz_resolve_idp_validation_failed",
            provider=body.provider,
            error=str(e),
            service=service_ctx.service_name,
        )
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Find or create user (JIT provisioning)
    user = await auth_service.find_or_create_user(
        db=db,
        provider=body.provider,
        provider_user_id=idp_claims["sub"],
        email=idp_claims["email"],
        name=idp_claims["name"],
        avatar_url=idp_claims.get("picture"),
    )

    if not user.is_active:
        logger.warning(
            "authz_resolve_inactive_user",
            user_id=str(user.id),
            email=user.email,
        )
        raise HTTPException(status_code=403, detail="User account is inactive")

    user_resp = AuthzUserResponse(id=user.id, email=user.email, name=user.name)

    # 3. If no workspace specified, return workspace list
    if not body.workspace_id:
        stmt = (
            select(Workspace, WorkspaceMembership.role)
            .join(WorkspaceMembership)
            .where(WorkspaceMembership.user_id == user.id)
            .order_by(Workspace.created_at)
        )
        result = await db.execute(stmt)
        workspaces = [
            AuthzWorkspaceOption(id=ws.id, name=ws.name, slug=ws.slug, role=role)
            for ws, role in result.all()
        ]
        return AuthzResolveResponse(user=user_resp, workspaces=workspaces)

    # 4. Resolve workspace membership
    stmt = select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == body.workspace_id,
        WorkspaceMembership.user_id == user.id,
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    if not membership:
        logger.warning(
            "authz_resolve_not_member",
            user_id=str(user.id),
            workspace_id=str(body.workspace_id),
        )
        raise HTTPException(
            status_code=403, detail="User is not a member of this workspace"
        )

    workspace = await db.get(Workspace, body.workspace_id)

    # 5. Get RBAC actions for this service
    actions = await get_user_actions(
        db, user.id, service_ctx.service_name, body.workspace_id
    )

    # 6. Sign authz JWT
    logger.info(
        "authz_token_issued",
        user_id=str(user.id),
        workspace_id=str(workspace.id),
        workspace_role=membership.role,
        service=service_ctx.service_name,
        actions_count=len(actions),
    )
    authz_token = create_authz_token(
        user_id=user.id,
        idp_sub=idp_claims["sub"],
        workspace_id=workspace.id,
        workspace_slug=workspace.slug,
        workspace_role=membership.role,
        actions=actions,
        service_name=service_ctx.service_name,
    )

    return AuthzResolveResponse(
        user=user_resp,
        workspace=AuthzWorkspaceResponse(
            id=workspace.id, slug=workspace.slug, role=membership.role
        ),
        authz_token=authz_token,
        expires_in=settings.authz_token_expire_minutes * 60,
    )
