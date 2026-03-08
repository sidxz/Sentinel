"""Dual-token middleware for AuthZ mode.

Validates both an IdP token (identity) and a Sentinel authz token
(authorization), checking that the idp_sub claims match.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import jwt
from jwt import PyJWKClient
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from sentinel_auth.types import AuthenticatedUser

if TYPE_CHECKING:
    from sentinel_auth.sentinel import Sentinel


class AuthzMiddleware(BaseHTTPMiddleware):
    """Validates IdP token + Sentinel authz token on each request.

    IdP token: ``Authorization: Bearer <idp_token>``
    Authz token: ``X-Authz-Token: <authz_token>``

    Both must be valid and their ``sub``/``idp_sub`` claims must match.

    The middleware accepts either explicit key strings or a ``Sentinel``
    instance.  When a ``Sentinel`` instance is provided the keys are read
    lazily so the middleware can be registered at import time before the
    lifespan fetches Sentinel's public key.

    For IdP token validation, you can provide either:
    - ``idp_public_key``: a single PEM-encoded public key
    - ``idp_jwks_url``: a JWKS endpoint URL (e.g. Google's) for automatic
      ``kid``-based key matching — handles key rotation gracefully
    """

    def __init__(
        self,
        app: ASGIApp,
        idp_public_key: str | None = None,
        idp_jwks_url: str | None = None,
        sentinel_public_key: str | None = None,
        sentinel_instance: Sentinel | None = None,
        idp_algorithm: str = "RS256",
        sentinel_algorithm: str = "RS256",
        sentinel_audience: str = "sentinel:authz",
        exclude_paths: list[str] | None = None,
    ):
        super().__init__(app)
        if not sentinel_public_key and not sentinel_instance:
            raise ValueError(
                "AuthzMiddleware requires either sentinel_public_key or sentinel_instance for authz token verification"
            )
        self._idp_public_key = idp_public_key
        self._idp_jwks_url = idp_jwks_url
        self._sentinel_public_key = sentinel_public_key
        self._sentinel_instance = sentinel_instance
        self.idp_algorithm = idp_algorithm
        self.sentinel_algorithm = sentinel_algorithm
        self.sentinel_audience = sentinel_audience
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/openapi.json"]

        # Build JWKS client for kid-based key lookup
        jwks_url = idp_jwks_url or (sentinel_instance.idp_jwks_url if sentinel_instance else None)
        self._idp_jwks_client: PyJWKClient | None = PyJWKClient(jwks_url) if jwks_url else None

    @property
    def idp_public_key(self) -> str:
        if self._idp_public_key:
            return self._idp_public_key
        if self._sentinel_instance:
            return self._sentinel_instance.idp_public_key or ""
        return ""

    @property
    def sentinel_public_key(self) -> str:
        key = self._sentinel_public_key
        if not key and self._sentinel_instance:
            key = self._sentinel_instance.sentinel_public_key or ""
        if not key:
            raise RuntimeError(
                "Sentinel public key not available. Ensure sentinel_instance.lifespan() has run "
                "or provide sentinel_public_key directly."
            )
        return key

    def _decode_idp_token(self, token: str) -> dict:
        """Decode and validate an IdP token using JWKS or static key."""
        if self._idp_jwks_client:
            signing_key = self._idp_jwks_client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=[self.idp_algorithm],
                options={"verify_aud": False},
            )
        return jwt.decode(
            token,
            self.idp_public_key,
            algorithms=[self.idp_algorithm],
            options={"verify_aud": False},
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        if any(request.url.path == p or request.url.path.startswith(p + "/") for p in self.exclude_paths):
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
            idp_payload = self._decode_idp_token(idp_token)
        except jwt.ExpiredSignatureError:
            return JSONResponse(status_code=401, content={"detail": "IdP token expired"})
        except jwt.InvalidTokenError:
            return JSONResponse(status_code=401, content={"detail": "Invalid IdP token"})

        # 4. Validate authz token
        try:
            authz_payload = jwt.decode(
                authz_token,
                self.sentinel_public_key,
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
