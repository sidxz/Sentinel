import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
from src.middleware.rate_limit import limiter, rate_limit_exceeded_handler
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
    logger.info("daikon-identity-service starting", port=settings.service_port)
    await _run_migrations()
    logger.info("database migrations applied")
    app.state.start_time = time.time()
    yield
    logger.info("daikon-identity-service shutting down")


app = FastAPI(
    title="Daikon Identity Service",
    description="Authentication, workspace management, and permissions",
    version="0.1.0",
    lifespan=lifespan,
)

# --- Middleware (applied bottom-to-top, so first added = outermost) ---

# Security headers on every response
app.add_middleware(SecurityHeadersMiddleware, hsts=settings.cookie_secure)

# Session middleware required by Authlib for OAuth2 state
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)

# Trusted host validation (prevents Host header attacks)
if settings.allowed_hosts != "*":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Service-Key"],
)

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
