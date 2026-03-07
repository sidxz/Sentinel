"""AuthZ Mode endpoints — IdP token validation + authorization JWT issuance."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import ServiceKeyContext, require_service_key
from src.auth.jwt import create_authz_token
from src.config import settings
from src.database import get_db
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


@router.post("/resolve", response_model=AuthzResolveResponse)
async def resolve(
    body: AuthzResolveRequest,
    service_ctx: ServiceKeyContext = Depends(require_service_key),
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
        raise HTTPException(
            status_code=403, detail="User is not a member of this workspace"
        )

    workspace = await db.get(Workspace, body.workspace_id)

    # 5. Get RBAC actions for this service
    actions = await get_user_actions(
        db, user.id, service_ctx.service_name, body.workspace_id
    )

    # 6. Sign authz JWT
    authz_token = create_authz_token(
        user_id=user.id,
        idp_sub=idp_claims["sub"],
        workspace_id=workspace.id,
        workspace_slug=workspace.slug,
        workspace_role=membership.role,
        actions=actions,
    )

    return AuthzResolveResponse(
        user=user_resp,
        workspace=AuthzWorkspaceResponse(
            id=workspace.id, slug=workspace.slug, role=membership.role
        ),
        authz_token=authz_token,
        expires_in=settings.authz_token_expire_minutes * 60,
    )
