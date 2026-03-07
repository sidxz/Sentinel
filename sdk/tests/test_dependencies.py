"""Tests for FastAPI dependency helpers."""

import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from sentinel_auth.auth import RequestAuth
from sentinel_auth.dependencies import (
    get_current_user,
    get_request_auth_factory,
    get_workspace_context,
    get_workspace_id,
    require_role,
)
from sentinel_auth.types import AuthenticatedUser

FAKE_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.fake"


def _inject_user(app: FastAPI, user: AuthenticatedUser, *, with_token: bool = False):
    """Middleware that injects a fake user into request.state (bypass JWT)."""

    @app.middleware("http")
    async def _set_user(request: Request, call_next):
        request.state.user = user
        if with_token:
            request.state.token = FAKE_TOKEN
        return await call_next(request)


@pytest.fixture()
def editor_user(user_id, workspace_id):
    return AuthenticatedUser(
        user_id=user_id,
        email="a@b.com",
        name="A",
        workspace_id=workspace_id,
        workspace_slug="acme",
        workspace_role="editor",
    )


class TestGetCurrentUser:
    def test_returns_user(self, editor_user):
        app = FastAPI()
        _inject_user(app, editor_user)

        @app.get("/me")
        def me(user: AuthenticatedUser = Depends(get_current_user)):
            return {"email": user.email}

        resp = TestClient(app).get("/me")
        assert resp.status_code == 200
        assert resp.json()["email"] == "a@b.com"

    def test_401_when_no_user(self):
        app = FastAPI()

        @app.get("/me")
        def me(user: AuthenticatedUser = Depends(get_current_user)):
            return {"email": user.email}

        resp = TestClient(app).get("/me")
        assert resp.status_code == 401


class TestGetWorkspaceId:
    def test_returns_workspace_id(self, editor_user, workspace_id):
        app = FastAPI()
        _inject_user(app, editor_user)

        @app.get("/wid")
        def wid(wid: uuid.UUID = Depends(get_workspace_id)):
            return {"wid": str(wid)}

        resp = TestClient(app).get("/wid")
        assert resp.json()["wid"] == str(workspace_id)


class TestGetWorkspaceContext:
    def test_returns_context(self, editor_user, workspace_id, user_id):
        app = FastAPI()
        _inject_user(app, editor_user)

        @app.get("/ctx")
        def ctx(ctx=Depends(get_workspace_context)):
            return {"wid": str(ctx.workspace_id), "role": ctx.role}

        resp = TestClient(app).get("/ctx")
        data = resp.json()
        assert data["wid"] == str(workspace_id)
        assert data["role"] == "editor"


class TestRequireRole:
    def test_passes_when_role_sufficient(self, editor_user):
        app = FastAPI()
        _inject_user(app, editor_user)

        @app.get("/edit")
        def edit(user: AuthenticatedUser = Depends(require_role("editor"))):
            return {"ok": True}

        assert TestClient(app).get("/edit").status_code == 200

    def test_rejects_when_role_insufficient(self, editor_user):
        app = FastAPI()
        _inject_user(app, editor_user)

        @app.get("/admin")
        def admin(user: AuthenticatedUser = Depends(require_role("admin"))):
            return {"ok": True}

        resp = TestClient(app).get("/admin")
        assert resp.status_code == 403
        assert "admin" in resp.json()["detail"]


class TestGetRequestAuth:
    def test_returns_request_auth_with_state_token(self, editor_user):
        """When middleware sets request.state.token, get_request_auth uses it."""
        app = FastAPI()
        _inject_user(app, editor_user, with_token=True)
        dep = get_request_auth_factory()

        @app.get("/auth")
        def auth_route(auth: RequestAuth = Depends(dep)):
            return {"user_id": str(auth.user_id), "email": auth.email}

        resp = TestClient(app).get("/auth")
        assert resp.status_code == 200
        assert resp.json()["email"] == "a@b.com"

    def test_fallback_to_authorization_header(self, editor_user):
        """When request.state.token is missing, extracts from Authorization header."""
        app = FastAPI()
        _inject_user(app, editor_user, with_token=False)
        dep = get_request_auth_factory()

        @app.get("/auth")
        def auth_route(auth: RequestAuth = Depends(dep)):
            return {"user_id": str(auth.user_id)}

        resp = TestClient(app).get("/auth", headers={"Authorization": f"Bearer {FAKE_TOKEN}"})
        assert resp.status_code == 200

    def test_401_when_no_token_anywhere(self, editor_user):
        """When no token on state or header, returns 401."""
        app = FastAPI()
        _inject_user(app, editor_user, with_token=False)
        dep = get_request_auth_factory()

        @app.get("/auth")
        def auth_route(auth: RequestAuth = Depends(dep)):
            return {"ok": True}

        resp = TestClient(app).get("/auth")
        assert resp.status_code == 401

    def test_wires_permission_and_role_clients(self, editor_user):
        """Clients passed to factory are available on the resulting RequestAuth."""
        from sentinel_auth.permissions import PermissionClient
        from sentinel_auth.roles import RoleClient

        pc = PermissionClient("https://auth.test", "svc", service_key="sk")
        rc = RoleClient("https://auth.test", "svc", service_key="sk")
        app = FastAPI()
        _inject_user(app, editor_user, with_token=True)
        dep = get_request_auth_factory(permissions=pc, roles=rc)

        @app.get("/auth")
        def auth_route(auth: RequestAuth = Depends(dep)):
            has_perms = auth._permissions is not None
            has_roles = auth._roles is not None
            return {"has_perms": has_perms, "has_roles": has_roles}

        resp = TestClient(app).get("/auth")
        assert resp.status_code == 200
        assert resp.json() == {"has_perms": True, "has_roles": True}
