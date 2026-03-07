# AuthZ Mode Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add AuthZ Mode to Sentinel — client apps authenticate directly with IdPs, Sentinel validates IdP tokens and issues authorization-only JWTs.

**Architecture:** New `/authz/resolve` endpoint accepts an IdP token + service key, validates the IdP token against the provider's JWKS, provisions the user, resolves workspace membership/roles, and returns a signed authz JWT. SDK gets a new dual-token middleware and `AuthzClient`. Existing proxy mode is untouched.

**Tech Stack:** FastAPI, Authlib (IdP token validation), PyJWT (authz JWT signing), httpx (JWKS fetching), existing Redis/PostgreSQL stack.

---

## Task 1: IdP Token Validator Service

Create a service that validates IdP tokens (Google OIDC, EntraID OIDC, GitHub OAuth) using each provider's JWKS or introspection endpoint.

**Files:**
- Create: `service/src/services/idp_validator.py`
- Create: `service/tests/test_idp_validator.py`

**Step 1: Write the failing test**

```python
# service/tests/test_idp_validator.py
"""Tests for IdP token validation."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from src.services.idp_validator import validate_idp_token, IdpValidationError


@pytest.fixture(scope="module")
def idp_keypair():
    """Simulate an IdP's signing key."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture()
def google_id_token(idp_keypair):
    """A valid Google-style OIDC ID token."""
    priv, _ = idp_keypair
    now = int(time.time())
    payload = {
        "iss": "https://accounts.google.com",
        "sub": "google|12345",
        "email": "alice@acme.com",
        "email_verified": True,
        "name": "Alice",
        "picture": "https://example.com/alice.jpg",
        "aud": "test-google-client-id",
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, priv, algorithm="RS256")


class TestValidateIdpToken:
    @pytest.mark.asyncio
    async def test_valid_google_token(self, idp_keypair, google_id_token):
        priv, pub = idp_keypair
        result = await validate_idp_token(
            idp_token=google_id_token,
            provider="google",
            _override_key=pub,  # test hook to skip JWKS fetch
        )
        assert result["email"] == "alice@acme.com"
        assert result["sub"] == "google|12345"
        assert result["name"] == "Alice"
        assert result["email_verified"] is True

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, idp_keypair):
        priv, pub = idp_keypair
        now = int(time.time())
        payload = {
            "iss": "https://accounts.google.com",
            "sub": "google|12345",
            "email": "alice@acme.com",
            "email_verified": True,
            "name": "Alice",
            "aud": "test-google-client-id",
            "iat": now - 7200,
            "exp": now - 3600,
        }
        token = jwt.encode(payload, priv, algorithm="RS256")
        with pytest.raises(IdpValidationError, match="expired"):
            await validate_idp_token(token, "google", _override_key=pub)

    @pytest.mark.asyncio
    async def test_unsupported_provider_rejected(self, google_id_token, idp_keypair):
        _, pub = idp_keypair
        with pytest.raises(IdpValidationError, match="Unsupported"):
            await validate_idp_token(google_id_token, "unsupported_provider", _override_key=pub)

    @pytest.mark.asyncio
    async def test_unverified_email_rejected(self, idp_keypair):
        priv, pub = idp_keypair
        now = int(time.time())
        payload = {
            "iss": "https://accounts.google.com",
            "sub": "google|12345",
            "email": "alice@acme.com",
            "email_verified": False,
            "name": "Alice",
            "aud": "test-google-client-id",
            "iat": now,
            "exp": now + 3600,
        }
        token = jwt.encode(payload, priv, algorithm="RS256")
        with pytest.raises(IdpValidationError, match="not verified"):
            await validate_idp_token(token, "google", _override_key=pub)
```

**Step 2: Run test to verify it fails**

Run: `cd service && uv run pytest tests/test_idp_validator.py -v`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

```python
# service/src/services/idp_validator.py
"""Validate IdP tokens (OIDC ID tokens or OAuth access tokens) against provider JWKS."""

import httpx
import jwt as pyjwt
from jwt.algorithms import RSAAlgorithm

from src.auth.providers import get_configured_providers
from src.config import settings


class IdpValidationError(Exception):
    """Raised when an IdP token fails validation."""


# JWKS cache: provider → list of public keys
_jwks_cache: dict[str, list] = {}

# Provider metadata
_PROVIDER_CONFIG = {
    "google": {
        "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
        "issuer": "https://accounts.google.com",
        "audience": lambda: settings.google_client_id,
    },
    "entra_id": {
        "jwks_uri": lambda: (
            f"https://login.microsoftonline.com/{settings.entra_tenant_id}"
            "/discovery/v2.0/keys"
        ),
        "issuer": lambda: (
            f"https://login.microsoftonline.com/{settings.entra_tenant_id}/v2.0"
        ),
        "audience": lambda: settings.entra_client_id,
    },
}


async def _fetch_jwks(provider: str) -> list:
    """Fetch and cache JWKS public keys for an OIDC provider."""
    if provider in _jwks_cache:
        return _jwks_cache[provider]

    config = _PROVIDER_CONFIG.get(provider)
    if not config:
        raise IdpValidationError(f"Unsupported provider: {provider}")

    jwks_uri = config["jwks_uri"]
    if callable(jwks_uri):
        jwks_uri = jwks_uri()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(jwks_uri)
        resp.raise_for_status()
        jwks = resp.json()

    keys = []
    for key_data in jwks.get("keys", []):
        if key_data.get("kty") == "RSA":
            keys.append(RSAAlgorithm.from_jwk(key_data))
    _jwks_cache[provider] = keys
    return keys


async def validate_idp_token(
    idp_token: str,
    provider: str,
    *,
    _override_key=None,
) -> dict:
    """Validate an IdP token and return normalized user claims.

    Args:
        idp_token: The raw JWT from the IdP (OIDC ID token).
        provider: Provider name ("google", "entra_id").
        _override_key: Test-only override to skip JWKS fetch.

    Returns:
        Dict with keys: sub, email, name, email_verified, picture (optional).

    Raises:
        IdpValidationError: If the token is invalid, expired, or from
            an unsupported provider.
    """
    configured = get_configured_providers()
    if provider not in configured and provider not in _PROVIDER_CONFIG:
        raise IdpValidationError(f"Unsupported provider: {provider}")

    # GitHub uses opaque tokens — validate via API, not JWT
    if provider == "github":
        return await _validate_github_token(idp_token)

    config = _PROVIDER_CONFIG.get(provider)
    if not config:
        raise IdpValidationError(f"Unsupported provider: {provider}")

    issuer = config["issuer"]
    if callable(issuer):
        issuer = issuer()
    audience = config["audience"]
    if callable(audience):
        audience = audience()

    # Get signing keys
    if _override_key:
        keys = [_override_key]
    else:
        keys = await _fetch_jwks(provider)

    # Try each key (key rotation means multiple valid keys)
    last_error = None
    for key in keys:
        try:
            payload = pyjwt.decode(
                idp_token,
                key,
                algorithms=["RS256"],
                audience=audience if not _override_key else None,
                issuer=issuer if not _override_key else None,
                options={
                    "verify_aud": not bool(_override_key),
                    "verify_iss": not bool(_override_key),
                },
            )
            break
        except pyjwt.ExpiredSignatureError:
            raise IdpValidationError("IdP token has expired")
        except pyjwt.InvalidTokenError as e:
            last_error = e
            continue
    else:
        raise IdpValidationError(f"IdP token signature invalid: {last_error}")

    # Require verified email
    if not payload.get("email_verified", False):
        raise IdpValidationError("Email not verified by IdP")

    return {
        "sub": payload.get("sub", ""),
        "email": payload.get("email", ""),
        "name": payload.get("name", ""),
        "email_verified": payload.get("email_verified", False),
        "picture": payload.get("picture"),
    }


async def _validate_github_token(access_token: str) -> dict:
    """Validate a GitHub OAuth access token via API introspection."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Get user profile
        resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code != 200:
            raise IdpValidationError("Invalid GitHub access token")
        profile = resp.json()

        # Get verified primary email
        resp = await client.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code != 200:
            raise IdpValidationError("Cannot retrieve GitHub emails")
        emails = resp.json()
        primary = next(
            (e for e in emails if e.get("primary") and e.get("verified")),
            None,
        )
        if not primary:
            raise IdpValidationError("Email not verified by IdP")

    return {
        "sub": f"github|{profile['id']}",
        "email": primary["email"],
        "name": profile.get("name") or profile.get("login", ""),
        "email_verified": True,
        "picture": profile.get("avatar_url"),
    }


def clear_jwks_cache() -> None:
    """Clear the JWKS cache (for testing or key rotation)."""
    _jwks_cache.clear()
```

**Step 4: Run test to verify it passes**

Run: `cd service && uv run pytest tests/test_idp_validator.py -v`
Expected: 4 tests PASS

**Step 5: Commit**

```bash
git add service/src/services/idp_validator.py service/tests/test_idp_validator.py
git commit -m "feat: add IdP token validator service for AuthZ mode"
```

---

## Task 2: Authz JWT Creation

Add a new `create_authz_token` function to the JWT module. Audience `sentinel:authz`, short-lived (5 min), contains workspace role + RBAC actions + `idp_sub` binding.

**Files:**
- Modify: `service/src/auth/jwt.py` — add `create_authz_token` + `_AUD_AUTHZ`
- Modify: `service/src/config.py` — add `authz_token_expire_minutes` setting
- Create: `service/tests/test_authz_jwt.py`

**Step 1: Write the failing test**

```python
# service/tests/test_authz_jwt.py
"""Tests for authz token creation and decoding."""

import uuid

import jwt as pyjwt
import pytest

from src.auth.jwt import _AUD_AUTHZ, create_authz_token, decode_token


class TestAuthzToken:
    def test_create_and_decode(self):
        user_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        token = create_authz_token(
            user_id=user_id,
            idp_sub="google|12345",
            workspace_id=workspace_id,
            workspace_slug="acme-corp",
            workspace_role="editor",
            actions=["read", "write"],
        )
        payload = decode_token(token, audience=_AUD_AUTHZ)
        assert payload["sub"] == str(user_id)
        assert payload["idp_sub"] == "google|12345"
        assert payload["wid"] == str(workspace_id)
        assert payload["wrole"] == "editor"
        assert payload["actions"] == ["read", "write"]
        assert payload["aud"] == "sentinel:authz"
        assert payload["type"] == "authz"

    def test_wrong_audience_rejected(self):
        token = create_authz_token(
            user_id=uuid.uuid4(),
            idp_sub="google|12345",
            workspace_id=uuid.uuid4(),
            workspace_slug="test",
            workspace_role="viewer",
            actions=[],
        )
        with pytest.raises(pyjwt.InvalidAudienceError):
            decode_token(token, audience="sentinel:access")
```

**Step 2: Run test to verify it fails**

Run: `cd service && uv run pytest tests/test_authz_jwt.py -v`
Expected: FAIL — `_AUD_AUTHZ` not found

**Step 3: Write implementation**

In `service/src/config.py`, add to the `Settings` class after `admin_token_expire_minutes`:
```python
    authz_token_expire_minutes: int = 5
```

In `service/src/auth/jwt.py`, add the audience constant and function:
```python
_AUD_AUTHZ = "sentinel:authz"

def create_authz_token(
    user_id: uuid.UUID,
    idp_sub: str,
    workspace_id: uuid.UUID,
    workspace_slug: str,
    workspace_role: str,
    actions: list[str],
) -> str:
    """Create a short-lived authorization-only JWT.

    This token carries workspace role and RBAC actions but NOT identity.
    Identity is proven by the IdP token (validated separately).
    The idp_sub claim binds this token to a specific IdP identity.
    """
    now = datetime.now(UTC)
    payload = {
        "iss": _ISSUER,
        "sub": str(user_id),
        "idp_sub": idp_sub,
        "wid": str(workspace_id),
        "wslug": workspace_slug,
        "wrole": workspace_role,
        "actions": actions,
        "aud": _AUD_AUTHZ,
        "iat": now,
        "exp": now + timedelta(minutes=settings.authz_token_expire_minutes),
        "type": "authz",
    }
    return jwt.encode(payload, _get_private_key(), algorithm=settings.jwt_algorithm)
```

**Step 4: Run test to verify it passes**

Run: `cd service && uv run pytest tests/test_authz_jwt.py -v`
Expected: 2 tests PASS

**Step 5: Commit**

```bash
git add service/src/auth/jwt.py service/src/config.py service/tests/test_authz_jwt.py
git commit -m "feat: add authz token type for AuthZ mode"
```

---

## Task 3: AuthZ Resolve Endpoint

The core endpoint: validates IdP token, provisions user, resolves workspace, issues authz JWT.

**Files:**
- Create: `service/src/api/authz_routes.py`
- Create: `service/src/schemas/authz.py`
- Modify: `service/src/main.py` — mount the router
- Create: `service/tests/test_authz_routes.py`

**Step 1: Write schemas**

```python
# service/src/schemas/authz.py
"""Schemas for AuthZ mode endpoints."""

import uuid

from pydantic import BaseModel, Field


class AuthzResolveRequest(BaseModel):
    idp_token: str = Field(description="Raw IdP token (OIDC ID token or OAuth access token)")
    provider: str = Field(description="IdP provider name: google, github, entra_id")
    workspace_id: uuid.UUID | None = Field(
        default=None,
        description="Workspace to authorize for. Omit for workspace list.",
    )


class AuthzUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str


class AuthzWorkspaceResponse(BaseModel):
    id: uuid.UUID
    slug: str
    role: str


class AuthzWorkspaceOption(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    role: str


class AuthzResolveResponse(BaseModel):
    user: AuthzUserResponse
    workspace: AuthzWorkspaceResponse | None = None
    authz_token: str | None = None
    expires_in: int | None = None
    workspaces: list[AuthzWorkspaceOption] | None = None
```

**Step 2: Write the endpoint**

```python
# service/src/api/authz_routes.py
"""AuthZ Mode endpoints — IdP token validation + authorization JWT issuance."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import ServiceKeyContext, require_service_key
from src.auth.jwt import create_authz_token
from src.config import settings
from src.database import get_db
from src.models.workspace import Workspace, WorkspaceMembership
from src.schemas.authz import (
    AuthzResolveRequest,
    AuthzResolveResponse,
    AuthzUserResponse,
    AuthzWorkspaceOption,
    AuthzWorkspaceResponse,
)
from src.services import auth_service
from src.services.idp_validator import IdpValidationError, validate_idp_token
from src.services.role_service import get_user_actions

logger = structlog.get_logger()

router = APIRouter(prefix="/authz", tags=["authz"])


@router.post("/resolve", response_model=AuthzResolveResponse)
async def resolve(
    body: AuthzResolveRequest,
    service_ctx: ServiceKeyContext = Depends(require_service_key),
    db: AsyncSession = Depends(get_db),
):
    """Validate IdP token, provision user, and return authorization context.

    If workspace_id is provided, returns a signed authz JWT for that workspace.
    If omitted, returns the list of workspaces the user belongs to.
    """
    # 1. Validate IdP token against provider's JWKS
    try:
        idp_claims = await validate_idp_token(body.idp_token, body.provider)
    except IdpValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Find or create user (JIT provisioning)
    user = await auth_service.find_or_create_user(
        db=db,
        provider=body.provider,
        provider_user_id=idp_claims["sub"],
        email=idp_claims["email"],
        name=idp_claims["name"],
        avatar_url=idp_claims.get("picture"),
    )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    user_resp = AuthzUserResponse(id=user.id, email=user.email, name=user.name)

    # 3. If no workspace specified, return workspace list
    if not body.workspace_id:
        stmt = (
            select(Workspace, WorkspaceMembership.role)
            .join(WorkspaceMembership)
            .where(WorkspaceMembership.user_id == user.id)
            .order_by(Workspace.created_at)
        )
        result = await db.execute(stmt)
        workspaces = [
            AuthzWorkspaceOption(id=ws.id, name=ws.name, slug=ws.slug, role=role)
            for ws, role in result.all()
        ]
        return AuthzResolveResponse(user=user_resp, workspaces=workspaces)

    # 4. Resolve workspace membership
    stmt = select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == body.workspace_id,
        WorkspaceMembership.user_id == user.id,
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=403, detail="User is not a member of this workspace"
        )

    workspace = await db.get(Workspace, body.workspace_id)

    # 5. Get RBAC actions for this service
    actions = await get_user_actions(
        db, user.id, service_ctx.service_name, body.workspace_id
    )

    # 6. Sign authz JWT
    authz_token = create_authz_token(
        user_id=user.id,
        idp_sub=idp_claims["sub"],
        workspace_id=workspace.id,
        workspace_slug=workspace.slug,
        workspace_role=membership.role,
        actions=actions,
    )

    return AuthzResolveResponse(
        user=user_resp,
        workspace=AuthzWorkspaceResponse(
            id=workspace.id, slug=workspace.slug, role=membership.role
        ),
        authz_token=authz_token,
        expires_in=settings.authz_token_expire_minutes * 60,
    )
```

**Step 3: Mount router in main.py**

Add to `service/src/main.py` alongside other router includes:
```python
from src.api.authz_routes import router as authz_router
app.include_router(authz_router)
```

**Step 4: Run lint**

Run: `make fmt && make lint`

**Step 5: Commit**

```bash
git add service/src/api/authz_routes.py service/src/schemas/authz.py service/src/main.py
git commit -m "feat: add /authz/resolve endpoint for AuthZ mode"
```

---

## Task 4: SDK AuthzClient

Client library for calling `/authz/resolve` from client apps.

**Files:**
- Create: `sdk/src/sentinel_auth/authz.py`
- Create: `sdk/tests/test_authz_client.py`

**Step 1: Write the test**

```python
# sdk/tests/test_authz_client.py
"""Tests for AuthzClient."""

import uuid

import pytest
import respx
from httpx import Response

from sentinel_auth.authz import AuthzClient


class TestAuthzClient:
    @pytest.mark.asyncio
    async def test_resolve_with_workspace(self):
        user_id = str(uuid.uuid4())
        workspace_id = str(uuid.uuid4())
        mock_response = {
            "user": {"id": user_id, "email": "alice@acme.com", "name": "Alice"},
            "workspace": {"id": workspace_id, "slug": "acme", "role": "editor"},
            "authz_token": "eyJ...",
            "expires_in": 300,
            "workspaces": None,
        }
        with respx.mock:
            respx.post("http://sentinel:9003/authz/resolve").mock(
                return_value=Response(200, json=mock_response)
            )
            async with AuthzClient("http://sentinel:9003", service_key="sk_test") as client:
                result = await client.resolve(
                    idp_token="fake-idp-token",
                    provider="google",
                    workspace_id=uuid.UUID(workspace_id),
                )
                assert result["authz_token"] == "eyJ..."
                assert result["user"]["email"] == "alice@acme.com"

    @pytest.mark.asyncio
    async def test_resolve_workspace_list(self):
        mock_response = {
            "user": {"id": str(uuid.uuid4()), "email": "alice@acme.com", "name": "Alice"},
            "workspaces": [
                {"id": str(uuid.uuid4()), "name": "Acme", "slug": "acme", "role": "editor"},
            ],
            "workspace": None,
            "authz_token": None,
            "expires_in": None,
        }
        with respx.mock:
            respx.post("http://sentinel:9003/authz/resolve").mock(
                return_value=Response(200, json=mock_response)
            )
            async with AuthzClient("http://sentinel:9003", service_key="sk_test") as client:
                result = await client.resolve(idp_token="fake", provider="google")
                assert len(result["workspaces"]) == 1
```

**Step 2: Write implementation**

```python
# sdk/src/sentinel_auth/authz.py
"""AuthZ mode client — resolve IdP tokens into authorization context."""

import uuid

import httpx

from sentinel_auth._utils import warn_if_insecure
from sentinel_auth.types import SentinelError


class AuthzClient:
    """Client for Sentinel's AuthZ mode endpoints.

    Validates IdP tokens and retrieves authorization context
    (workspace roles, RBAC actions, signed authz JWT).
    """

    def __init__(self, base_url: str, service_key: str):
        self.base_url = base_url.rstrip("/")
        self.service_key = service_key
        self._client: httpx.AsyncClient | None = None
        warn_if_insecure(self.base_url, "AuthzClient")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    def _headers(self) -> dict[str, str]:
        return {"X-Service-Key": self.service_key}

    async def resolve(
        self,
        idp_token: str,
        provider: str,
        workspace_id: uuid.UUID | None = None,
    ) -> dict:
        """Resolve an IdP token into authorization context.

        Args:
            idp_token: Raw token from the IdP (OIDC ID token or OAuth access token).
            provider: IdP provider name ("google", "github", "entra_id").
            workspace_id: Optional workspace to authorize for.

        Returns:
            Dict with user info. If workspace_id was provided, includes
            authz_token and workspace. Otherwise includes workspaces list.
        """
        client = await self._get_client()
        body: dict = {"idp_token": idp_token, "provider": provider}
        if workspace_id:
            body["workspace_id"] = str(workspace_id)
        resp = await client.post(
            f"{self.base_url}/authz/resolve",
            json=body,
            headers=self._headers(),
        )
        if resp.status_code != 200:
            raise SentinelError(resp.status_code, resp.text)
        return resp.json()

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
```

**Step 3: Run tests**

Run: `cd sdk && uv run pytest tests/test_authz_client.py -v`
Expected: 2 tests PASS

**Step 4: Commit**

```bash
git add sdk/src/sentinel_auth/authz.py sdk/tests/test_authz_client.py
git commit -m "feat: add AuthzClient to SDK for AuthZ mode"
```

---

## Task 5: SDK Dual-Token Middleware

Middleware that validates both IdP token (identity) and Sentinel authz token (authorization), checking the `idp_sub` binding.

**Files:**
- Create: `sdk/src/sentinel_auth/authz_middleware.py`
- Create: `sdk/tests/test_authz_middleware.py`

**Step 1: Write the test**

```python
# sdk/tests/test_authz_middleware.py
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


@pytest.fixture()
def dual_tokens(idp_keypair, sentinel_keypair):
    idp_priv, _ = idp_keypair
    sentinel_priv, _ = sentinel_keypair
    now = datetime.datetime.now(datetime.UTC)
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    idp_sub = "google|12345"

    idp_token = pyjwt.encode(
        {"sub": idp_sub, "email": "alice@acme.com", "iat": now, "exp": now + datetime.timedelta(hours=1)},
        idp_priv, algorithm="RS256",
    )
    authz_token = pyjwt.encode(
        {
            "sub": str(user_id), "idp_sub": idp_sub,
            "wid": str(workspace_id), "wslug": "acme", "wrole": "editor",
            "actions": ["read"], "aud": "sentinel:authz",
            "iat": now, "exp": now + datetime.timedelta(minutes=5),
        },
        sentinel_priv, algorithm="RS256",
    )
    return idp_token, authz_token


def _make_app(idp_pub_key: str, sentinel_pub_key: str) -> Starlette:
    async def protected(request: Request) -> JSONResponse:
        user = request.state.user
        return JSONResponse({"email": user.email, "role": user.workspace_role})

    app = Starlette(routes=[Route("/protected", protected)])
    app.add_middleware(
        AuthzMiddleware,
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
            {"sub": "google|ATTACKER", "email": "evil@evil.com", "iat": now, "exp": now + datetime.timedelta(hours=1)},
            idp_priv, algorithm="RS256",
        )
        authz_token = pyjwt.encode(
            {
                "sub": str(uuid.uuid4()), "idp_sub": "google|VICTIM",
                "wid": str(uuid.uuid4()), "wslug": "acme", "wrole": "owner",
                "actions": [], "aud": "sentinel:authz",
                "iat": now, "exp": now + datetime.timedelta(minutes=5),
            },
            sentinel_priv, algorithm="RS256",
        )
        client = TestClient(_make_app(idp_pub, sentinel_pub))
        resp = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {idp_token}", "X-Authz-Token": authz_token},
        )
        assert resp.status_code == 401
        assert "binding" in resp.json()["detail"].lower()
```

**Step 2: Write implementation**

```python
# sdk/src/sentinel_auth/authz_middleware.py
"""Dual-token middleware for AuthZ mode.

Validates both an IdP token (identity) and a Sentinel authz token
(authorization), checking that the idp_sub claims match.
"""

import uuid

import jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from sentinel_auth.types import AuthenticatedUser


class AuthzMiddleware(BaseHTTPMiddleware):
    """Validates IdP token + Sentinel authz token on each request.

    IdP token: ``Authorization: Bearer <idp_token>``
    Authz token: ``X-Authz-Token: <authz_token>``

    Both must be valid and their ``sub``/``idp_sub`` claims must match.
    """

    def __init__(
        self,
        app: ASGIApp,
        idp_public_key: str,
        sentinel_public_key: str,
        idp_algorithm: str = "RS256",
        sentinel_algorithm: str = "RS256",
        sentinel_audience: str = "sentinel:authz",
        exclude_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.idp_public_key = idp_public_key
        self.sentinel_public_key = sentinel_public_key
        self.idp_algorithm = idp_algorithm
        self.sentinel_algorithm = sentinel_algorithm
        self.sentinel_audience = sentinel_audience
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/openapi.json"]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if any(request.url.path.startswith(p) for p in self.exclude_paths):
            return await call_next(request)

        # 1. Extract IdP token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing IdP token"})
        idp_token = auth_header.removeprefix("Bearer ")

        # 2. Extract authz token from X-Authz-Token header
        authz_token = request.headers.get("X-Authz-Token")
        if not authz_token:
            return JSONResponse(status_code=401, content={"detail": "Missing authz token"})

        # 3. Validate IdP token
        try:
            idp_payload = jwt.decode(
                idp_token, self.idp_public_key,
                algorithms=[self.idp_algorithm],
                options={"verify_aud": False},
            )
        except jwt.ExpiredSignatureError:
            return JSONResponse(status_code=401, content={"detail": "IdP token expired"})
        except jwt.InvalidTokenError:
            return JSONResponse(status_code=401, content={"detail": "Invalid IdP token"})

        # 4. Validate authz token
        try:
            authz_payload = jwt.decode(
                authz_token, self.sentinel_public_key,
                algorithms=[self.sentinel_algorithm],
                audience=self.sentinel_audience,
            )
        except jwt.ExpiredSignatureError:
            return JSONResponse(status_code=401, content={"detail": "Authz token expired"})
        except jwt.InvalidTokenError:
            return JSONResponse(status_code=401, content={"detail": "Invalid authz token"})

        # 5. Verify binding: IdP sub must match authz idp_sub
        idp_sub = idp_payload.get("sub", "")
        authz_idp_sub = authz_payload.get("idp_sub", "")
        if idp_sub != authz_idp_sub:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token binding mismatch: idp_sub does not match"},
            )

        # 6. Set user on request state
        try:
            request.state.user = AuthenticatedUser(
                user_id=uuid.UUID(authz_payload["sub"]),
                email=idp_payload.get("email", ""),
                name=idp_payload.get("name", ""),
                workspace_id=uuid.UUID(authz_payload["wid"]),
                workspace_slug=authz_payload.get("wslug", ""),
                workspace_role=authz_payload["wrole"],
                groups=[],
            )
            request.state.token = authz_token
            request.state.idp_token = idp_token
        except (KeyError, ValueError):
            return JSONResponse(status_code=401, content={"detail": "Invalid token claims"})

        return await call_next(request)
```

**Step 3: Run tests**

Run: `cd sdk && uv run pytest tests/test_authz_middleware.py -v`
Expected: 3 tests PASS

**Step 4: Commit**

```bash
git add sdk/src/sentinel_auth/authz_middleware.py sdk/tests/test_authz_middleware.py
git commit -m "feat: add dual-token AuthZ middleware to SDK"
```

---

## Task 6: Sentinel Class AuthZ Mode Support

Extend the `Sentinel` class to support `mode="authz"` — uses `AuthzMiddleware` + `AuthzClient` instead of `JWTAuthMiddleware`.

**Files:**
- Modify: `sdk/src/sentinel_auth/sentinel.py` — add mode parameter, authz client, protect logic
- Modify: `sdk/src/sentinel_auth/__init__.py` — export new classes

**Step 1: Modify Sentinel class**

Add to `__init__` parameters:
```python
    mode: str = "proxy",  # "proxy" (default) or "authz"
    idp_jwks_url: str | None = None,  # Required for mode="authz"
    idp_public_key: str | None = None,  # Alternative to idp_jwks_url
```

Add `authz` property:
```python
    @property
    def authz(self) -> AuthzClient:
        if self._authz is None:
            self._authz = AuthzClient(self.base_url, self.service_key)
        return self._authz
```

In `protect()`, branch on mode:
```python
    if self.mode == "authz":
        app.add_middleware(
            AuthzMiddleware,
            idp_public_key=self.idp_public_key,
            sentinel_public_key=self._sentinel_public_key,
            exclude_paths=exclude_paths,
        )
    else:
        app.add_middleware(
            JWTAuthMiddleware,
            base_url=self.base_url,
            exclude_paths=exclude_paths,
        )
```

**Step 2: Export new classes from `__init__.py`**

Add to exports:
```python
from sentinel_auth.authz import AuthzClient
from sentinel_auth.authz_middleware import AuthzMiddleware
```

**Step 3: Run all SDK tests**

Run: `cd sdk && uv run pytest -v`
Expected: All tests PASS (existing + new)

**Step 4: Commit**

```bash
git add sdk/src/sentinel_auth/sentinel.py sdk/src/sentinel_auth/__init__.py
git commit -m "feat: add mode='authz' support to Sentinel class"
```

---

## Task 7: Documentation + Lint + Final Verification

**Files:**
- Already created: `docs/architecture/authz-mode.md`
- Modify: `service/src/schemas/validators.py` — verify no issues
- Run full test suites and lint

**Step 1: Run all service tests**

Run: `cd service && uv run pytest tests/ -v`

**Step 2: Run all SDK tests**

Run: `cd sdk && uv run pytest -v`

**Step 3: Run lint**

Run: `make fmt && make lint`

**Step 4: Final commit**

```bash
git add docs/architecture/authz-mode.md
git commit -m "docs: add AuthZ mode architecture documentation"
```

---

## Verification

### Unit tests
- `service/tests/test_idp_validator.py` — IdP token validation (4 tests)
- `service/tests/test_authz_jwt.py` — Authz JWT creation/decoding (2 tests)
- `sdk/tests/test_authz_client.py` — AuthzClient HTTP calls (2 tests)
- `sdk/tests/test_authz_middleware.py` — Dual-token middleware (3 tests)

### Integration test (manual)
1. `make start` — start Sentinel
2. Get a real Google IdP token (via test app or OAuth playground)
3. `curl -X POST http://localhost:9003/authz/resolve -H "X-Service-Key: sk_..." -H "Content-Type: application/json" -d '{"idp_token": "...", "provider": "google"}'`
4. Verify: user created in DB, workspace list returned
5. Repeat with `workspace_id` — verify authz JWT returned
6. Decode authz JWT — verify `idp_sub`, `wrole`, `actions` claims

### Security verification
- Expired IdP token → 400
- Wrong provider → 400
- Unverified email → 400
- Invalid service key → 401
- User not in workspace → 403
- Mismatched `idp_sub` in middleware → 401
