"""Tests for JWTAuthMiddleware."""

import datetime

import respx
from httpx import Response
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

    def test_middleware_sets_token_on_state(self, rsa_keypair, valid_token):
        """After successful auth, request.state.token should contain the raw JWT."""
        _, pub = rsa_keypair

        async def check_token(request: Request) -> JSONResponse:
            return JSONResponse({"has_token": hasattr(request.state, "token"), "token": request.state.token})

        app = Starlette(routes=[Route("/check", check_token)])
        app.add_middleware(JWTAuthMiddleware, public_key=pub)
        client = TestClient(app)
        resp = client.get("/check", headers={"Authorization": f"Bearer {valid_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_token"] is True
        assert data["token"] == valid_token


def _make_jwks_app(base_url: str) -> Starlette:
    async def protected(request: Request) -> JSONResponse:
        return JSONResponse({"email": request.state.user.email})

    app = Starlette(routes=[Route("/protected", protected)])
    app.add_middleware(JWTAuthMiddleware, base_url=base_url)
    return app


def _jwks_for(public_pem: str, kid: str) -> dict:
    import json

    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from jwt.algorithms import RSAAlgorithm

    jwk = json.loads(RSAAlgorithm.to_jwk(load_pem_public_key(public_pem.encode())))
    jwk.update({"use": "sig", "alg": "RS256", "kid": kid})
    return {"keys": [jwk]}


class TestJWKSRotation:
    @respx.mock
    def test_selects_key_by_kid_from_jwks(self, rsa_keypair, jwt_payload):
        import jwt as pyjwt

        priv, pub = rsa_keypair
        token = pyjwt.encode(jwt_payload, priv, algorithm="RS256", headers={"kid": "key-1"})
        respx.get("http://sentinel/.well-known/jwks.json").mock(
            return_value=Response(200, json=_jwks_for(pub, "key-1"))
        )
        client = TestClient(_make_jwks_app("http://sentinel"))
        resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    @respx.mock
    def test_refetches_jwks_on_unknown_kid(self, rsa_keypair, jwt_payload):
        """After the keyset is cached, a token with a new (rotated-in) kid must
        trigger exactly one JWKS refetch and then validate."""
        import jwt as pyjwt
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa as rsa_mod

        old_priv, old_pub = rsa_keypair
        new = rsa_mod.generate_private_key(public_exponent=65537, key_size=2048)
        new_pub = new.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        new_priv = new.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        ).decode()

        respx.get("http://sentinel/.well-known/jwks.json").mock(
            side_effect=[
                Response(200, json=_jwks_for(old_pub, "old")),  # initial fetch
                Response(200, json=_jwks_for(new_pub, "new")),  # refetch after rotation
            ]
        )
        token_old = pyjwt.encode(jwt_payload, old_priv, algorithm="RS256", headers={"kid": "old"})
        token_new = pyjwt.encode(jwt_payload, new_priv, algorithm="RS256", headers={"kid": "new"})
        app = _make_jwks_app("http://sentinel")
        client = TestClient(app)

        # First request caches the "old" keyset.
        assert client.get("/protected", headers={"Authorization": f"Bearer {token_old}"}).status_code == 200
        # Rotated-in "new" kid is unknown → triggers a refetch → validates.
        assert client.get("/protected", headers={"Authorization": f"Bearer {token_new}"}).status_code == 200
