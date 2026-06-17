import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt import _AUD_ACCESS, _AUD_ADMIN, _AUD_AUTHZ, decode_token
from src.database import get_db
from src.middleware.request_context import bind_identity


@dataclass(frozen=True)
class CurrentUser:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    workspace_role: str
    groups: list[uuid.UUID]


@dataclass(frozen=True)
class ServiceKeyContext:
    """Resolved service identity from X-Service-Key header or Origin."""

    service_name: str  # bound service name, or "" in dev mode
    origin_authenticated: bool = False  # True when resolved via Origin, not service key
    # The calling app's registered IdP audience(s) (its OIDC client_id(s)). Empty =>
    # not configured => IdP-token validation falls back to the deployment-wide audience.
    # Used by /authz/resolve to bind an IdP token to the app it was issued for.
    allowed_idp_audiences: tuple[str, ...] = ()


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
        service_name, app_id = result
        bind_identity(request, caller_service=service_name)
        audiences = await service_app_service.get_idp_audiences(db, app_id)
        return ServiceKeyContext(
            service_name=service_name, allowed_idp_audiences=audiences
        )

    # 2. Try origin (browser frontends) — lower trust than service key
    origin = request.headers.get("Origin")
    if origin:
        result = await service_app_service.validate_origin(origin, db)
        if result:
            service_name, app_id = result
            bind_identity(request, caller_service=service_name)
            audiences = await service_app_service.get_idp_audiences(db, app_id)
            return ServiceKeyContext(
                service_name=service_name,
                origin_authenticated=True,
                allowed_idp_audiences=audiences,
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


async def require_admin(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
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

    from src.services.token_service import (
        is_access_token_blacklisted,
        is_user_deactivated,
    )

    # Check admin token revocation (jti denylist)
    if jti := payload.get("jti"):
        if await is_access_token_blacklisted(jti):
            raise HTTPException(status_code=401, detail="Token has been revoked")

    # Re-check user is active + still admin at request time. Flipping is_admin or
    # is_active must take effect immediately, not only after the cookie expires.
    user_id = payload.get("sub")
    if user_id:
        if await is_user_deactivated(user_id):
            raise HTTPException(status_code=401, detail="User account is deactivated")
        from src.models.user import User

        user = await db.get(User, uuid.UUID(user_id))
        if user is None or not user.is_active or not user.is_admin:
            raise HTTPException(status_code=401, detail="Admin privileges revoked")

    # CSRF: require X-Requested-With header on state-changing methods
    if request.method in ("POST", "PATCH", "PUT", "DELETE"):
        if not request.headers.get("X-Requested-With"):
            raise HTTPException(
                status_code=403, detail="Missing X-Requested-With header"
            )

    identity_kwargs: dict = {}
    if actor := payload.get("sub"):
        identity_kwargs["actor"] = actor
    if wid := payload.get("wid"):
        identity_kwargs["workspace_id"] = str(wid)
    if identity_kwargs:
        bind_identity(request, **identity_kwargs)

    return payload


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

    await _enforce_token_hygiene(payload)

    current_user = CurrentUser(
        user_id=uuid.UUID(payload["sub"]),
        workspace_id=uuid.UUID(payload["wid"]),
        workspace_role=payload["wrole"],
        groups=[uuid.UUID(g) for g in payload.get("groups", [])],
    )
    bind_identity(
        request,
        actor=str(current_user.user_id),
        workspace_id=str(current_user.workspace_id),
    )
    return current_user


async def _enforce_token_hygiene(payload: dict) -> None:
    """Revocation + deactivation checks common to every user-bearing token.

    Applies to both access and authz tokens. Historically the authz-token path
    skipped these, leaving issued tokens valid until their TTL even after the
    user was deactivated — now fixed.
    """
    from src.services.token_service import (
        is_access_token_blacklisted,
        is_user_deactivated,
    )

    if jti := payload.get("jti"):
        if await is_access_token_blacklisted(jti):
            raise HTTPException(status_code=401, detail="Token has been revoked")
    if user_id := payload.get("sub"):
        if await is_user_deactivated(user_id):
            raise HTTPException(status_code=401, detail="User account is deactivated")


async def get_user_for_service_call(
    request: Request,
    svc_ctx: ServiceKeyContext = Depends(require_service_key),
) -> CurrentUser:
    """Extract user context from Bearer JWT — accepts access or authz tokens.

    Pair with dual-auth endpoints. In proxy mode, services forward the user's
    access token; in authz mode, services forward the authz token instead. The
    service key establishes trust; this extracts user identity and — for authz
    tokens — enforces the ``svc`` claim matches the calling service so a token
    minted for service A cannot be replayed on service B.
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

    await _enforce_token_hygiene(payload)

    if token_type == "authz":
        token_svc = payload.get("svc")
        if not token_svc or token_svc != svc_ctx.service_name:
            raise HTTPException(
                status_code=403,
                detail="Authz token was issued for a different service",
            )

    bind_identity(
        request,
        actor=payload["sub"],
        workspace_id=payload["wid"],
        caller_service=svc_ctx.service_name,
    )
    return CurrentUser(
        user_id=uuid.UUID(payload["sub"]),
        workspace_id=uuid.UUID(payload["wid"]),
        workspace_role=payload["wrole"],
        groups=[uuid.UUID(g) for g in payload.get("groups", [])],
    )


async def get_current_user_flexible(
    request: Request, db: AsyncSession = Depends(get_db)
) -> CurrentUser:
    """Extract user context — accepts access tokens always, authz tokens only with valid service key.

    Use this on endpoints that need to work in both proxy mode (browser → access token)
    and authz mode (backend → service key + authz token).

    Security: authz tokens are only accepted when X-Service-Key is present AND
    validated against the database. The service key's ``service_name`` MUST equal
    the authz token's ``svc`` claim — otherwise the token was minted for a
    different service and must not be accepted.
    """
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = auth.removeprefix("Bearer ")
    if len(token) > 8192:
        raise HTTPException(status_code=401, detail="Token too large")

    # Validate the service key against the database — not just check for presence
    service_key_service_name: str | None = None
    raw_key = request.headers.get("X-Service-Key")
    if raw_key:
        from src.services import service_app_service

        result = await service_app_service.validate_key(raw_key, db)
        if result is not None:
            service_key_service_name = result[0]

    has_valid_service_key = service_key_service_name is not None
    audiences = [_AUD_ACCESS, _AUD_AUTHZ] if has_valid_service_key else _AUD_ACCESS

    try:
        payload = decode_token(token, audience=audiences)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    token_type = payload.get("type")
    valid_types = ("access", "authz") if has_valid_service_key else ("access",)
    if token_type not in valid_types:
        raise HTTPException(status_code=401, detail="Invalid token type")

    if not all(k in payload for k in ("sub", "wid", "wrole")):
        raise HTTPException(status_code=401, detail="Token missing required claims")

    await _enforce_token_hygiene(payload)

    if token_type == "authz":
        token_svc = payload.get("svc")
        if not token_svc or token_svc != service_key_service_name:
            raise HTTPException(
                status_code=403,
                detail="Authz token was issued for a different service",
            )

    bind_identity(
        request,
        actor=payload["sub"],
        workspace_id=payload["wid"],
        caller_service=service_key_service_name,
    )
    return CurrentUser(
        user_id=uuid.UUID(payload["sub"]),
        workspace_id=uuid.UUID(payload["wid"]),
        workspace_role=payload["wrole"],
        groups=[uuid.UUID(g) for g in payload.get("groups", [])],
    )
