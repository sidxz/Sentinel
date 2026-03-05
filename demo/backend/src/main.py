"""Team Notes — demo app showcasing the Daikon Identity SDK."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from identity_sdk.middleware import JWTAuthMiddleware
from identity_sdk.permissions import PermissionClient
from identity_sdk.roles import RoleClient

from src.config import settings

PUBLIC_KEY = settings.public_key_path.read_text()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SDK clients
    app.state.permissions = PermissionClient(
        base_url=settings.identity_service_url,
        service_name=settings.service_name,
        service_key=settings.service_api_key or None,
    )
    app.state.roles = RoleClient(
        base_url=settings.identity_service_url,
        service_name=settings.service_name,
        service_key=settings.service_api_key or None,
    )

    # Register RBAC actions on startup (idempotent)
    try:
        await app.state.roles.register_actions([
            {"action": "notes:export", "description": "Export notes as JSON"},
            {"action": "notes:bulk-delete", "description": "Bulk delete notes"},
        ])
    except Exception:
        pass  # Identity service may not be reachable yet

    yield

    await app.state.permissions.close()
    await app.state.roles.close()


app = FastAPI(
    title="Team Notes",
    description="Demo app showcasing the Daikon Identity SDK — "
    "workspace isolation, role enforcement, entity ACLs, and custom RBAC.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for the demo frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT authentication — validates Bearer tokens on every request
app.add_middleware(
    JWTAuthMiddleware,
    public_key=PUBLIC_KEY,
    exclude_paths=["/health", "/docs", "/openapi.json", "/redoc"],
)

# Mount routes
from src.routes import router  # noqa: E402

app.include_router(router)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "team-notes-demo"}


if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("TEAM NOTES — Daikon Identity SDK Demo")
    print("=" * 60)
    print(f"\nIdentity service: {settings.identity_service_url}")
    print(f"Demo backend:     http://localhost:{settings.port}")
    print(f"Demo frontend:    {settings.frontend_url}")
    print(f"\nAPI docs: http://localhost:{settings.port}/docs")
    print("=" * 60 + "\n")

    uvicorn.run("src.main:app", host=settings.host, port=settings.port, reload=True)
