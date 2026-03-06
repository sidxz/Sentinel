import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from src.api.admin_routes import router as admin_router
from src.api.auth_routes import router as auth_router
from src.api.group_routes import router as group_router
from src.api.permission_routes import router as permission_router
from src.api.role_routes import router as role_router
from src.api.user_routes import router as user_router
from src.api.workspace_routes import router as workspace_router
from slowapi.errors import RateLimitExceeded

from src.config import settings
from src.middleware.rate_limit import (
    GlobalRateLimitMiddleware,
    limiter,
    rate_limit_exceeded_handler,
)
from src.middleware.cors import DynamicCORSMiddleware, refresh_origins
from src.middleware.security_headers import MaxBodySizeMiddleware, SecurityHeadersMiddleware

logger = structlog.get_logger()


async def _run_migrations():
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    from alembic import command
    from alembic.config import Config

    def _migrate():
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=1) as pool:
        await loop.run_in_executor(pool, _migrate)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("daikon-sentinel starting", port=settings.service_port)
    await _run_migrations()
    logger.info("database migrations applied")

    # Warm CORS origin cache from active client apps
    from src.database import engine as db_engine

    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(db_engine) as db:
        await refresh_origins(db)

    # Security checks — fail-closed in production, warn in dev
    _insecure_session = (
        settings.session_secret_key == "dev-only-change-me-in-production"
    )
    _insecure_cookie = not settings.cookie_secure

    # Check service apps in DB
    from src.services import service_app_service

    async with AsyncSession(db_engine) as db:
        _no_service_apps = not await service_app_service.has_active_apps(db)

    # Redis connectivity and auth check
    _redis_down = False
    _redis_no_auth = False
    _redis_no_tls = False
    try:
        from src.services.token_service import get_redis

        r = await get_redis()
        await r.ping()
        if "@" not in settings.redis_url:
            _redis_no_auth = True
        if not settings.redis_url.startswith("rediss://"):
            _redis_no_tls = True
    except Exception:
        _redis_down = True

    if not settings.debug:
        errors = []
        if _insecure_session:
            errors.append("SESSION_SECRET_KEY is using the default dev value")
        if _no_service_apps:
            errors.append(
                "No active service apps registered — all service-key endpoints will return 401"
            )
        if _insecure_cookie:
            errors.append("COOKIE_SECURE is False — cookies will be sent over HTTP")
        if _redis_down:
            errors.append(
                "Redis is unreachable — auth codes, refresh tokens, and denylist will fail"
            )
        if _redis_no_auth:
            errors.append(
                "Redis URL has no authentication — set a password in REDIS_URL (redis://:password@host:port/db)"
            )
        if _redis_no_tls:
            logger.warning(
                "Redis URL is not using TLS — use rediss:// if Redis is outside a trusted network"
            )
        if "*" in settings.allowed_hosts_list:
            errors.append(
                "ALLOWED_HOSTS is wildcard — set explicit hosts via ALLOWED_HOSTS or BASE_URL/ADMIN_URL"
            )
        if errors:
            for e in errors:
                logger.critical(e)
            raise RuntimeError(
                "Refusing to start: insecure configuration with DEBUG=False. "
                f"Fix: {'; '.join(errors)}"
            )
    else:
        if _insecure_session:
            logger.warning(
                "SESSION_SECRET_KEY is using the default dev value — set a random secret in production"
            )
        if _no_service_apps:
            logger.warning(
                "No active service apps registered — service-key endpoints will return 401. "
                "Create one via the admin panel (/admin/service-apps)"
            )
        if _insecure_cookie:
            logger.warning(
                "COOKIE_SECURE is False — admin cookies will be sent over HTTP"
            )
        if _redis_down:
            logger.warning("Redis is unreachable — some features will not work")
        if _redis_no_auth:
            logger.warning(
                "Redis URL has no authentication — use redis://:password@host in production"
            )
        if _redis_no_tls:
            logger.warning(
                "Redis URL is not using TLS — use rediss:// in production"
            )

    app.state.start_time = time.time()
    yield
    logger.info("daikon-sentinel shutting down")


app = FastAPI(
    title="Sentinel Auth",
    description="Authentication, workspace management, and permissions",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# --- Middleware (last added = outermost, processes request first) ---

# Reject oversized request bodies (10 MB)
app.add_middleware(MaxBodySizeMiddleware, max_bytes=10_485_760)

# Global rate limiting (30 req/min per IP, all endpoints)
app.add_middleware(GlobalRateLimitMiddleware, requests_per_minute=30)

# Security headers on every response
app.add_middleware(SecurityHeadersMiddleware, hsts=settings.cookie_secure)

# Session middleware required by Authlib for OAuth2 state
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    https_only=settings.cookie_secure,
    same_site="lax",
    max_age=600,  # 10 min — bounds the OAuth flow window
)

# Trusted host validation (prevents Host header attacks)
if "*" not in settings.allowed_hosts_list:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)

app.add_middleware(DynamicCORSMiddleware)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(workspace_router)
app.include_router(group_router)
app.include_router(permission_router)
app.include_router(role_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/.well-known/jwks.json", tags=["auth"])
async def jwks():
    from src.auth.jwks import build_jwks

    return build_jwks()
