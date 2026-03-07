import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt import _AUD_ACCESS, _AUD_ADMIN, decode_token
from src.database import get_db


async def require_admin(request: Request) -> dict:
    """FastAPI dependency that requires a valid admin JWT cookie."""
    token = request.cookies.get("admin_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(token, audience=_AUD_ADMIN)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not payload.get("admin"):
        raise HTTPException(status_code=403, detail="Not an admin")

    # Check admin token revocation (jti denylist)
    if jti := payload.get("jti"):
        from src.services.token_service import is_access_token_blacklisted

        if await is_access_token_blacklisted(jti):
            raise HTTPException(status_code=401, detail="Token has been revoked")

    # CSRF: require X-Requested-With header on state-changing methods
    if request.method in ("POST", "PATCH", "PUT", "DELETE"):
        if not request.headers.get("X-Requested-With"):
            raise HTTPException(
                status_code=403, detail="Missing X-Requested-With header"
            )

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
        payload = decode_token(token, audience=_AUD_ACCESS)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

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


@dataclass(frozen=True)
class ServiceKeyContext:
    """Resolved service identity from X-Service-Key header."""

    service_name: str  # bound service name, or "" in dev mode


async def require_service_key(
    request: Request, db: AsyncSession = Depends(get_db)
) -> ServiceKeyContext:
    """FastAPI dependency: validate X-Service-Key header against DB.

    Always requires a valid service key. Register service apps via the admin
    panel (/admin/service-apps).
    Returns a ServiceKeyContext with the bound service_name.
    """
    from src.services import service_app_service

    key = request.headers.get("X-Service-Key")
    if not key:
        raise HTTPException(
            status_code=401, detail="Invalid or missing service API key"
        )
    result = await service_app_service.validate_key(key, db)
    if not result:
        raise HTTPException(
            status_code=401, detail="Invalid or missing service API key"
        )
    service_name, _app_id = result
    return ServiceKeyContext(service_name=service_name)


def verify_service_scope(ctx: ServiceKeyContext, service_name: str) -> None:
    """Verify the service key is scoped to the requested service_name."""
    if ctx.service_name != service_name:
        raise HTTPException(
            status_code=403,
            detail=f"Service key is not authorized for service '{service_name}'",
        )


async def require_service_context(
    request: Request, db: AsyncSession = Depends(get_db)
) -> ServiceKeyContext:
    """Resolve service identity from X-Service-Key header OR Origin header.

    Backends send X-Service-Key. Browser frontends are identified by
    matching the Origin header against ServiceApp.allowed_origins.
    """
    from src.services import service_app_service

    # 1. Try service key (backends)
    key = request.headers.get("X-Service-Key")
    if key:
        result = await service_app_service.validate_key(key, db)
        if not result:
            raise HTTPException(
                status_code=401, detail="Invalid or missing service API key"
            )
        service_name, _app_id = result
        return ServiceKeyContext(service_name=service_name)

    # 2. Try origin (browser frontends)
    origin = request.headers.get("Origin")
    if origin:
        result = await service_app_service.validate_origin(origin, db)
        if result:
            service_name, _app_id = result
            return ServiceKeyContext(service_name=service_name)

    raise HTTPException(
        status_code=401,
        detail="Missing service API key or unregistered origin",
    )
