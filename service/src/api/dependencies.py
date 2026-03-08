import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt import _AUD_ACCESS, _AUD_ADMIN, _AUD_AUTHZ, decode_token
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
    if len(token) > 8192:
        raise HTTPException(status_code=401, detail="Token too large")
    try:
        # Security: only accept access tokens — authz tokens must not be usable here
        payload = decode_token(token, audience=_AUD_ACCESS)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Security: enforce token type to prevent cross-type confusion
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    # Security: reject tokens missing required claims
    if not all(k in payload for k in ("sub", "wid", "wrole")):
        raise HTTPException(status_code=401, detail="Token missing required claims")

    # Check token revocation (jti denylist)
    if jti := payload.get("jti"):
        from src.services.token_service import is_access_token_blacklisted

        if await is_access_token_blacklisted(jti):
            raise HTTPException(status_code=401, detail="Token has been revoked")

    # Security: reject deactivated users even if JWT is still valid
    user_id = payload.get("sub")
    if user_id:
        from src.services.token_service import is_user_deactivated

        if await is_user_deactivated(user_id):
            raise HTTPException(status_code=401, detail="User account is deactivated")

    return CurrentUser(
        user_id=uuid.UUID(payload["sub"]),
        workspace_id=uuid.UUID(payload["wid"]),
        workspace_role=payload["wrole"],
        groups=[uuid.UUID(g) for g in payload.get("groups", [])],
    )


async def get_user_for_service_call(request: Request) -> CurrentUser:
    """Extract user context from Bearer JWT — accepts access or authz tokens.

    Use this ONLY on endpoints that also require service key auth (dual-auth).
    In proxy mode, services forward the user's access token.
    In authz mode, services forward the authz token instead.
    The service key establishes trust; this just extracts user identity.
    """
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = auth.removeprefix("Bearer ")
    if len(token) > 8192:
        raise HTTPException(status_code=401, detail="Token too large")
    try:
        payload = decode_token(token, audience=[_AUD_ACCESS, _AUD_AUTHZ])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    token_type = payload.get("type")
    if token_type not in ("access", "authz"):
        raise HTTPException(status_code=401, detail="Invalid token type")

    # Security: reject tokens missing required claims
    if not all(k in payload for k in ("sub", "wid", "wrole")):
        raise HTTPException(status_code=401, detail="Token missing required claims")

    # For access tokens, check revocation and deactivation
    if token_type == "access":
        if jti := payload.get("jti"):
            from src.services.token_service import is_access_token_blacklisted

            if await is_access_token_blacklisted(jti):
                raise HTTPException(status_code=401, detail="Token has been revoked")

        user_id = payload.get("sub")
        if user_id:
            from src.services.token_service import is_user_deactivated

            if await is_user_deactivated(user_id):
                raise HTTPException(
                    status_code=401, detail="User account is deactivated"
                )

    return CurrentUser(
        user_id=uuid.UUID(payload["sub"]),
        workspace_id=uuid.UUID(payload["wid"]),
        workspace_role=payload["wrole"],
        groups=[uuid.UUID(g) for g in payload.get("groups", [])],
    )


@dataclass(frozen=True)
class ServiceKeyContext:
    """Resolved service identity from X-Service-Key header or Origin."""

    service_name: str  # bound service name, or "" in dev mode
    origin_authenticated: bool = False  # True when resolved via Origin, not service key


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

    # 2. Try origin (browser frontends) — lower trust than service key
    origin = request.headers.get("Origin")
    if origin:
        result = await service_app_service.validate_origin(origin, db)
        if result:
            service_name, _app_id = result
            return ServiceKeyContext(
                service_name=service_name, origin_authenticated=True
            )

    raise HTTPException(
        status_code=401,
        detail="Missing service API key or unregistered origin",
    )


async def require_service_key(
    ctx: ServiceKeyContext = Depends(require_service_context),
) -> ServiceKeyContext:
    """FastAPI dependency: require service key authentication (not Origin).

    Wraps require_service_context but rejects Origin-based resolution.
    Use this for endpoints that need strict service-to-service auth.
    """
    # Security: Origin-based auth is lower trust — reject for service key-only endpoints
    if ctx.origin_authenticated:
        raise HTTPException(status_code=401, detail="Service key required")
    return ctx
