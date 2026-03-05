"""Tests for JWTAuthMiddleware."""

import datetime

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from sentinel_auth.middleware import JWTAuthMiddleware


def _make_app(public_key: str) -> Starlette:
    async def protected(request: Request) -> JSONResponse:
        user = request.state.user
        return JSONResponse({"email": user.email, "role": user.workspace_role})

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/protected", protected), Route("/health", health)])
    app.add_middleware(JWTAuthMiddleware, public_key=public_key)
    return app


class TestJWTMiddleware:
    def test_valid_token(self, rsa_keypair, valid_token):
        _, pub = rsa_keypair
        client = TestClient(_make_app(pub))
        resp = client.get("/protected", headers={"Authorization": f"Bearer {valid_token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "alice@example.com"

    def test_missing_auth_header(self, rsa_keypair):
        _, pub = rsa_keypair
        client = TestClient(_make_app(pub))
        resp = client.get("/protected")
        assert resp.status_code == 401
        assert "Missing" in resp.json()["detail"]

    def test_expired_token(self, rsa_keypair, jwt_payload, make_token):
        _, pub = rsa_keypair
        jwt_payload["exp"] = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
        token = make_token(jwt_payload)
        client = TestClient(_make_app(pub))
        resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
        assert "expired" in resp.json()["detail"]

    def test_invalid_signature(self, rsa_keypair, valid_token):
        # Use a different key to verify — should fail
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa as rsa_mod

        other_key = rsa_mod.generate_private_key(public_exponent=65537, key_size=2048)
        other_pub = (
            other_key.public_key()
            .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
            .decode()
        )
        client = TestClient(_make_app(other_pub))
        resp = client.get("/protected", headers={"Authorization": f"Bearer {valid_token}"})
        assert resp.status_code == 401
        assert "Invalid token" in resp.json()["detail"]

    def test_excluded_path_skips_auth(self, rsa_keypair):
        _, pub = rsa_keypair
        client = TestClient(_make_app(pub))
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_malformed_bearer(self, rsa_keypair):
        _, pub = rsa_keypair
        client = TestClient(_make_app(pub))
        resp = client.get("/protected", headers={"Authorization": "Basic abc"})
        assert resp.status_code == 401

    def test_allowed_workspaces_permits_matching(self, rsa_keypair, valid_token, workspace_id):
        _, pub = rsa_keypair
        app = _make_app(pub)
        # Re-create with allowed_workspaces containing the token's workspace
        app = Starlette(routes=[Route("/protected", _make_app(pub).routes[0].endpoint)])
        app.add_middleware(JWTAuthMiddleware, public_key=pub, allowed_workspaces={str(workspace_id)})
        client = TestClient(app)
        resp = client.get("/protected", headers={"Authorization": f"Bearer {valid_token}"})
        assert resp.status_code == 200

    def test_allowed_workspaces_rejects_non_matching(self, rsa_keypair, valid_token):
        _, pub = rsa_keypair
        app = Starlette(routes=[Route("/protected", _make_app(pub).routes[0].endpoint)])
        allowed = {"00000000-0000-0000-0000-000000000000"}
        app.add_middleware(JWTAuthMiddleware, public_key=pub, allowed_workspaces=allowed)
        client = TestClient(app)
        resp = client.get("/protected", headers={"Authorization": f"Bearer {valid_token}"})
        assert resp.status_code == 403
        assert "Workspace not permitted" in resp.json()["detail"]

    def test_allowed_workspaces_none_allows_all(self, rsa_keypair, valid_token):
        _, pub = rsa_keypair
        # Default behavior (None) — should allow any workspace
        client = TestClient(_make_app(pub))
        resp = client.get("/protected", headers={"Authorization": f"Bearer {valid_token}"})
        assert resp.status_code == 200
