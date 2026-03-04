from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from src.api.admin_routes import router as admin_router
from src.api.auth_routes import router as auth_router
from src.api.group_routes import router as group_router
from src.api.permission_routes import router as permission_router
from src.api.user_routes import router as user_router
from src.api.workspace_routes import router as workspace_router
from src.config import settings

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
    yield
    logger.info("daikon-identity-service shutting down")


app = FastAPI(
    title="Daikon Identity Service",
    description="Authentication, workspace management, and permissions",
    version="0.1.0",
    lifespan=lifespan,
)

# Session middleware required by Authlib for OAuth2 state
app.add_middleware(SessionMiddleware, secret_key="change-me-in-production")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(workspace_router)
app.include_router(group_router)
app.include_router(permission_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
