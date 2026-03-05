import uuid
from dataclasses import dataclass

from fastapi import HTTPException, Request

from src.auth.jwt import decode_token
from src.config import settings


async def require_admin(request: Request) -> dict:
    """FastAPI dependency that requires a valid admin JWT cookie."""
    token = request.cookies.get("admin_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not payload.get("admin"):
        raise HTTPException(status_code=403, detail="Not an admin")

    # Check admin token revocation (jti denylist)
    if jti := payload.get("jti"):
        from src.services.token_service import is_access_token_blacklisted

        if await is_access_token_blacklisted(jti):
            raise HTTPException(status_code=401, detail="Token has been revoked")

    return payload


@dataclass(frozen=True)
class CurrentUser:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    workspace_role: str
    groups: list[uuid.UUID]


async def get_current_user(request: Request) -> CurrentUser:
    """FastAPI dependency: extract user context from Bearer JWT."""
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = auth.removeprefix("Bearer ")
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    # Check token revocation (jti denylist)
    if jti := payload.get("jti"):
        from src.services.token_service import is_access_token_blacklisted

        if await is_access_token_blacklisted(jti):
            raise HTTPException(status_code=401, detail="Token has been revoked")

    return CurrentUser(
        user_id=uuid.UUID(payload["sub"]),
        workspace_id=uuid.UUID(payload["wid"]),
        workspace_role=payload["wrole"],
        groups=[uuid.UUID(g) for g in payload.get("groups", [])],
    )


async def require_service_key(request: Request) -> str:
    """FastAPI dependency: validate X-Service-Key header.

    When SERVICE_API_KEYS is empty (dev mode), all requests pass through.
    In production, requests without a valid key get 401.
    """
    allowed = settings.service_api_key_set
    if not allowed:
        return ""
    key = request.headers.get("X-Service-Key")
    if not key or key not in allowed:
        raise HTTPException(
            status_code=401, detail="Invalid or missing service API key"
        )
    return key
