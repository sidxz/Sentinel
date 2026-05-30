"""Tests for dual-token AuthZ middleware."""

import datetime
import uuid

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from sentinel_auth.authz_middleware import AuthzMiddleware


@pytest.fixture(scope="module")
def idp_keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key, key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()


@pytest.fixture(scope="module")
def sentinel_keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key, key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()


TEST_IDP_AUDIENCE = "my-oauth-client.apps.googleusercontent.com"
TEST_SERVICE_NAME = "team-notes"


@pytest.fixture()
def dual_tokens(idp_keypair, sentinel_keypair):
    idp_priv, _ = idp_keypair
    sentinel_priv, _ = sentinel_keypair
    now = datetime.datetime.now(datetime.UTC)
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    idp_sub = "google|12345"

    idp_token = pyjwt.encode(
        {
            "sub": idp_sub,
            "aud": TEST_IDP_AUDIENCE,
            "email": "alice@acme.com",
            "name": "Alice",
            "iat": now,
            "exp": now + datetime.timedelta(hours=1),
        },
        idp_priv,
        algorithm="RS256",
    )
    authz_token = pyjwt.encode(
        {
            "sub": str(user_id),
            "idp_sub": idp_sub,
            "svc": TEST_SERVICE_NAME,
            "wid": str(workspace_id),
            "wslug": "acme",
            "wrole": "editor",
            "actions": ["read"],
            "aud": "sentinel:authz",
            "iat": now,
            "exp": now + datetime.timedelta(minutes=5),
        },
        sentinel_priv,
        algorithm="RS256",
    )
    return idp_token, authz_token


def _make_app(idp_pub_key: str, sentinel_pub_key: str) -> Starlette:
    async def protected(request: Request) -> JSONResponse:
        user = request.state.user
        return JSONResponse({"email": user.email, "role": user.workspace_role})

    app = Starlette(routes=[Route("/protected", protected)])
    app.add_middleware(
        AuthzMiddleware,
        service_name=TEST_SERVICE_NAME,
        idp_audience=TEST_IDP_AUDIENCE,
        idp_public_key=idp_pub_key,
        sentinel_public_key=sentinel_pub_key,
    )
    return app


class TestAuthzMiddleware:
    def test_valid_dual_tokens(self, idp_keypair, sentinel_keypair, dual_tokens):
        _, idp_pub = idp_keypair
        _, sentinel_pub = sentinel_keypair
        idp_token, authz_token = dual_tokens
        client = TestClient(_make_app(idp_pub, sentinel_pub))
        resp = client.get(
            "/protected",
            headers={
                "Authorization": f"Bearer {idp_token}",
                "X-Authz-Token": authz_token,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "alice@acme.com"
        assert resp.json()["role"] == "editor"

    def test_missing_authz_token(self, idp_keypair, sentinel_keypair, dual_tokens):
        _, idp_pub = idp_keypair
        _, sentinel_pub = sentinel_keypair
        idp_token, _ = dual_tokens
        client = TestClient(_make_app(idp_pub, sentinel_pub))
        resp = client.get("/protected", headers={"Authorization": f"Bearer {idp_token}"})
        assert resp.status_code == 401

    def test_mismatched_idp_sub_rejected(self, idp_keypair, sentinel_keypair):
        idp_priv, idp_pub = idp_keypair
        sentinel_priv, sentinel_pub = sentinel_keypair
        now = datetime.datetime.now(datetime.UTC)

        idp_token = pyjwt.encode(
            {
                "sub": "google|ATTACKER",
                "aud": TEST_IDP_AUDIENCE,
                "email": "evil@evil.com",
                "iat": now,
                "exp": now + datetime.timedelta(hours=1),
            },
            idp_priv,
            algorithm="RS256",
        )
        authz_token = pyjwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "idp_sub": "google|VICTIM",
                "svc": TEST_SERVICE_NAME,
                "wid": str(uuid.uuid4()),
                "wslug": "acme",
                "wrole": "owner",
                "actions": [],
                "aud": "sentinel:authz",
                "iat": now,
                "exp": now + datetime.timedelta(minutes=5),
            },
            sentinel_priv,
            algorithm="RS256",
        )
        client = TestClient(_make_app(idp_pub, sentinel_pub))
        resp = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {idp_token}", "X-Authz-Token": authz_token},
        )
        assert resp.status_code == 401
        assert "binding" in resp.json()["detail"].lower()

    def test_wrong_audience_rejected(self, idp_keypair, sentinel_keypair, dual_tokens):
        """An IdP token with the wrong aud must be rejected even if signature is valid."""
        idp_priv, idp_pub = idp_keypair
        _, sentinel_pub = sentinel_keypair
        _, authz_token = dual_tokens
        now = datetime.datetime.now(datetime.UTC)

        # Valid signature, valid sub, but audience = attacker's OAuth client
        bad_audience_token = pyjwt.encode(
            {
                "sub": "google|12345",
                "aud": "attacker-client-id.apps.googleusercontent.com",
                "email": "alice@acme.com",
                "iat": now,
                "exp": now + datetime.timedelta(hours=1),
            },
            idp_priv,
            algorithm="RS256",
        )
        client = TestClient(_make_app(idp_pub, sentinel_pub))
        resp = client.get(
            "/protected",
            headers={
                "Authorization": f"Bearer {bad_audience_token}",
                "X-Authz-Token": authz_token,
            },
        )
        assert resp.status_code == 401

    def test_wrong_svc_rejected(self, idp_keypair, sentinel_keypair):
        """An authz token with a different svc claim must be rejected."""
        idp_priv, idp_pub = idp_keypair
        sentinel_priv, sentinel_pub = sentinel_keypair
        now = datetime.datetime.now(datetime.UTC)
        idp_sub = "google|12345"

        idp_token = pyjwt.encode(
            {
                "sub": idp_sub,
                "aud": TEST_IDP_AUDIENCE,
                "email": "alice@acme.com",
                "iat": now,
                "exp": now + datetime.timedelta(hours=1),
            },
            idp_priv,
            algorithm="RS256",
        )
        # Token minted for another service
        authz_token = pyjwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "idp_sub": idp_sub,
                "svc": "other-service",
                "wid": str(uuid.uuid4()),
                "wslug": "acme",
                "wrole": "owner",
                "actions": [],
                "aud": "sentinel:authz",
                "iat": now,
                "exp": now + datetime.timedelta(minutes=5),
            },
            sentinel_priv,
            algorithm="RS256",
        )
        client = TestClient(_make_app(idp_pub, sentinel_pub))
        resp = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {idp_token}", "X-Authz-Token": authz_token},
        )
        assert resp.status_code == 403
        assert "different service" in resp.json()["detail"].lower()


class _FakeSentinel:
    """Minimal stand-in exposing the keyset interface AuthzMiddleware needs."""

    def __init__(self, keyset):
        self._keyset = keyset
        self.fetch_calls = 0
        self.idp_public_key = None
        self.idp_jwks_url = None
        self.sentinel_public_key = None

    @property
    def sentinel_keyset(self):
        return self._keyset

    async def fetch_sentinel_keyset(self):
        self.fetch_calls += 1
        return self._keyset


def _signed_dual(idp_priv, sentinel_priv, kid):
    now = datetime.datetime.now(datetime.UTC)
    idp_sub = "google|12345"
    idp_token = pyjwt.encode(
        {
            "sub": idp_sub,
            "aud": TEST_IDP_AUDIENCE,
            "email": "alice@acme.com",
            "name": "Alice",
            "iat": now,
            "exp": now + datetime.timedelta(hours=1),
        },
        idp_priv,
        algorithm="RS256",
    )
    authz_token = pyjwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "idp_sub": idp_sub,
            "svc": TEST_SERVICE_NAME,
            "wid": str(uuid.uuid4()),
            "wslug": "acme",
            "wrole": "editor",
            "actions": ["read"],
            "aud": "sentinel:authz",
            "iat": now,
            "exp": now + datetime.timedelta(minutes=5),
        },
        sentinel_priv,
        algorithm="RS256",
        headers={"kid": kid},
    )
    return idp_token, authz_token


def _make_keyset_app(idp_pub, fake_sentinel) -> Starlette:
    async def protected(request: Request) -> JSONResponse:
        return JSONResponse({"email": request.state.user.email})

    app = Starlette(routes=[Route("/protected", protected)])
    app.add_middleware(
        AuthzMiddleware,
        service_name=TEST_SERVICE_NAME,
        idp_audience=TEST_IDP_AUDIENCE,
        idp_public_key=idp_pub,
        sentinel_instance=fake_sentinel,
    )
    return app


class TestAuthzKidRotation:
    def test_authz_token_selected_by_kid(self, idp_keypair, sentinel_keypair):
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        idp_priv, idp_pub = idp_keypair
        sentinel_priv, sentinel_pub = sentinel_keypair
        fake = _FakeSentinel({"s1": load_pem_public_key(sentinel_pub.encode())})
        idp_token, authz_token = _signed_dual(idp_priv, sentinel_priv, "s1")
        client = TestClient(_make_keyset_app(idp_pub, fake))
        resp = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {idp_token}", "X-Authz-Token": authz_token},
        )
        assert resp.status_code == 200
        assert fake.fetch_calls == 0

    def test_unknown_kid_triggers_keyset_refetch(self, idp_keypair, sentinel_keypair):
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        idp_priv, idp_pub = idp_keypair
        sentinel_priv, sentinel_pub = sentinel_keypair
        fake = _FakeSentinel({})  # cached keyset is empty
        real = {"s1": load_pem_public_key(sentinel_pub.encode())}

        async def _fetch():
            fake.fetch_calls += 1
            fake._keyset = real
            return real

        fake.fetch_sentinel_keyset = _fetch
        idp_token, authz_token = _signed_dual(idp_priv, sentinel_priv, "s1")
        client = TestClient(_make_keyset_app(idp_pub, fake))
        resp = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {idp_token}", "X-Authz-Token": authz_token},
        )
        assert resp.status_code == 200
        assert fake.fetch_calls == 1
