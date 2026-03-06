"""Team Notes — demo app showcasing the Sentinel Auth SDK."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentinel_auth.middleware import JWTAuthMiddleware
from sentinel_auth.permissions import PermissionClient
from sentinel_auth.roles import RoleClient

from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SDK clients
    app.state.permissions = PermissionClient(
        base_url=settings.sentinel_url,
        service_name=settings.service_name,
        service_key=settings.service_api_key or None,
    )
    app.state.roles = RoleClient(
        base_url=settings.sentinel_url,
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
        pass  # Sentinel service may not be reachable yet

    yield

    await app.state.permissions.close()
    await app.state.roles.close()


app = FastAPI(
    title="Team Notes",
    description="Demo app showcasing the Sentinel Auth SDK — "
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

# JWT authentication — fetches signing key from Sentinel JWKS on first request
app.add_middleware(
    JWTAuthMiddleware,
    jwks_url=f"{settings.sentinel_url}/.well-known/jwks.json",
    exclude_paths=["/health", "/docs", "/openapi.json", "/redoc"],
    allowed_workspaces=set(settings.allowed_workspaces) or None,
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
    print("TEAM NOTES — Sentinel Auth SDK Demo")
    print("=" * 60)
    print(f"\nSentinel service: {settings.sentinel_url}")
    print(f"Demo backend:     http://localhost:{settings.port}")
    print(f"Demo frontend:    {settings.frontend_url}")
    print(f"\nAPI docs: http://localhost:{settings.port}/docs")
    print("=" * 60 + "\n")

    uvicorn.run("src.main:app", host=settings.host, port=settings.port, reload=True)
