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
from src.middleware.security_headers import SecurityHeadersMiddleware

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

    # Security warnings
    if settings.session_secret_key == "dev-only-change-me-in-production":
        logger.warning(
            "SESSION_SECRET_KEY is using the default dev value — set a random secret in production"
        )
    if not settings.service_api_key_set:
        logger.warning(
            "SERVICE_API_KEYS is empty — all service-key checks are bypassed"
        )
    if not settings.cookie_secure:
        logger.warning("COOKIE_SECURE is False — admin cookies will be sent over HTTP")

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

# --- Middleware (applied bottom-to-top, so first added = outermost) ---

# Global rate limiting (30 req/min per IP, all endpoints)
app.add_middleware(GlobalRateLimitMiddleware, requests_per_minute=30)

# Security headers on every response
app.add_middleware(SecurityHeadersMiddleware, hsts=settings.cookie_secure)

# Session middleware required by Authlib for OAuth2 state
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)

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
