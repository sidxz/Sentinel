import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, get_current_user, require_service_key
from src.database import get_db
from src.schemas.role import (
    CheckActionRequest,
    CheckActionResponse,
    RegisterActionsRequest,
    ServiceActionResponse,
    UserActionsResponse,
)
from src.services import role_service

router = APIRouter(prefix="/roles", tags=["roles"])


# --- Service-only auth: service key ---


@router.post(
    "/actions/register", response_model=list[ServiceActionResponse], status_code=201
)
async def register_actions(
    body: RegisterActionsRequest,
    _key: str = Depends(require_service_key),
    db: AsyncSession = Depends(get_db),
):
    actions = await role_service.register_actions(
        db,
        service_name=body.service_name,
        actions=[
            {"action": a.action, "description": a.description} for a in body.actions
        ],
    )
    return actions


# --- Dual auth: service key + user JWT ---


@router.post("/check-action", response_model=CheckActionResponse)
async def check_action(
    body: CheckActionRequest,
    _key: str = Depends(require_service_key),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.workspace_id != user.workspace_id:
        raise HTTPException(status_code=403, detail="Cross-workspace check not allowed")

    allowed, roles = await role_service.check_action(
        db,
        user_id=user.user_id,
        service_name=body.service_name,
        action=body.action,
        workspace_id=body.workspace_id,
    )
    return CheckActionResponse(allowed=allowed, roles=roles)


@router.get("/user-actions", response_model=UserActionsResponse)
async def get_user_actions(
    workspace_id: uuid.UUID = Query(...),
    service_name: str = Query(...),
    _key: str = Depends(require_service_key),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if workspace_id != user.workspace_id:
        raise HTTPException(
            status_code=403, detail="Cross-workspace lookup not allowed"
        )

    actions = await role_service.get_user_actions(
        db,
        user_id=user.user_id,
        service_name=service_name,
        workspace_id=workspace_id,
    )
    return UserActionsResponse(actions=actions)
