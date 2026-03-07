"""Team Notes (AuthZ Mode) — demo app showcasing Sentinel dual-token auth.

In this mode:
  1. The client app authenticates users directly with an IdP (e.g. Google)
  2. The client calls Sentinel's /authz/resolve with the IdP token
  3. Sentinel validates the IdP token and returns an authorization JWT
  4. The client sends BOTH tokens to this backend on every request
  5. AuthzMiddleware validates both tokens and checks idp_sub binding
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import sentinel, settings

app = FastAPI(
    title="Team Notes (AuthZ Mode)",
    description="Demo app showcasing Sentinel AuthZ mode — dual-token validation, "
    "workspace roles, entity ACLs, and custom RBAC.",
    version="0.1.0",
    lifespan=sentinel.lifespan,
)

# Dual-token authentication (IdP token + Sentinel authz token)
sentinel.protect(app, exclude_paths=["/health", "/docs", "/openapi.json", "/redoc"])

# CORS must be added AFTER auth middleware so it wraps it (outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
from src.routes import router  # noqa: E402

app.include_router(router)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "team-notes-authz-demo"}


if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("TEAM NOTES — Sentinel AuthZ Mode Demo")
    print("=" * 60)
    print(f"\nSentinel service: {settings.sentinel_url}")
    print(f"Demo backend:     http://localhost:{settings.port}")
    print(f"Demo frontend:    {settings.frontend_url}")
    print(f"\nMode: authz (dual-token)")
    print(f"  - IdP token:   Authorization: Bearer <idp_token>")
    print(f"  - Authz token: X-Authz-Token: <authz_token>")
    print(f"\nAPI docs: http://localhost:{settings.port}/docs")
    print("=" * 60 + "\n")

    uvicorn.run("src.main:app", host=settings.host, port=settings.port, reload=True)
