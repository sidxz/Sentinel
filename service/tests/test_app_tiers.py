"""create_app(tier) mounts the right routers + middleware per listener tier.

Apps are inspected at CONSTRUCTION time — building a FastAPI app does not run its
lifespan, so no DB/Redis is touched. 'all' (the default) must carry every route so
dev/make-start/tests are unchanged; 'public' drops the service-key surface; 'internal'
drops the browser surface AND the Session/CORS middleware.
"""

import pytest
from starlette.middleware.sessions import SessionMiddleware

from src.main import INTERNAL_ROUTERS, PUBLIC_ROUTERS, _resolve_tier, create_app
from src.middleware.cors import DynamicCORSMiddleware


def _paths(app) -> set[str]:
    # FastAPI 0.138+ stores include_router results as _IncludedRouter (lazy),
    # so we walk into original_router.routes to collect real APIRoute paths.
    result: set[str] = set()
    for r in app.routes:
        if type(r).__name__ == "_IncludedRouter":
            for sub in r.original_router.routes:
                result.add(getattr(sub, "path", ""))
        else:
            result.add(getattr(r, "path", ""))
    return result


def _has_prefix(app, prefix: str) -> bool:
    return any(p == prefix or p.startswith(prefix + "/") for p in _paths(app))


def test_public_tier_has_browser_routes_not_service_key_surface():
    app = create_app("public")
    assert _has_prefix(app, "/auth")  # auth proxy — public
    assert _has_prefix(app, "/admin")  # admin — public
    assert _has_prefix(app, "/users")  # public
    # Service-key surface must be ABSENT from the public listener:
    assert not _has_prefix(app, "/authz")
    assert not _has_prefix(app, "/permissions")
    assert not _has_prefix(app, "/realm")
    assert not _has_prefix(app, "/roles")


def test_internal_tier_has_service_key_surface_not_browser_routes():
    app = create_app("internal")
    assert _has_prefix(app, "/authz")
    assert _has_prefix(app, "/permissions")
    assert _has_prefix(app, "/realm")  # Plan 2 router, mounted here
    assert _has_prefix(app, "/roles")
    # Browser surface must be ABSENT from the internal listener:
    assert not _has_prefix(app, "/auth")  # note: /authz is present, /auth is not
    assert not _has_prefix(app, "/admin")
    assert not _has_prefix(app, "/users")
    assert not _has_prefix(app, "/workspaces")


def test_all_tier_is_todays_app_superset():
    app = create_app("all")
    for prefix in (
        "/auth",
        "/admin",
        "/users",
        "/workspaces",
        "/authz",
        "/permissions",
        "/realm",
        "/roles",
    ):
        assert _has_prefix(app, prefix), prefix


def test_health_on_every_tier():
    for tier in ("public", "internal", "all"):
        assert "/health" in _paths(create_app(tier))


def test_jwks_public_and_all_not_internal():
    assert "/.well-known/jwks.json" in _paths(create_app("public"))
    assert "/.well-known/jwks.json" in _paths(create_app("all"))
    assert "/.well-known/jwks.json" not in _paths(create_app("internal"))


def test_internal_tier_drops_session_and_cors_middleware():
    internal = {m.cls for m in create_app("internal").user_middleware}
    assert SessionMiddleware not in internal
    assert DynamicCORSMiddleware not in internal
    public = {m.cls for m in create_app("public").user_middleware}
    assert SessionMiddleware in public
    assert DynamicCORSMiddleware in public


def test_realm_router_is_internal_only():
    from src.api.realm_routes import router as realm_router

    assert realm_router in INTERNAL_ROUTERS
    assert realm_router not in PUBLIC_ROUTERS


def test_resolve_tier_default_is_all(monkeypatch):
    monkeypatch.delenv("TIER", raising=False)
    assert _resolve_tier() == "all"


def test_resolve_tier_rejects_unknown(monkeypatch):
    monkeypatch.setenv("TIER", "bogus")
    with pytest.raises(RuntimeError):
        _resolve_tier()
