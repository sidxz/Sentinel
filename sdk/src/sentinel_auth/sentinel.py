"""Sentinel autoconfig — single entry point for integrating FastAPI apps."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from jwt.algorithms import RSAAlgorithm

from sentinel_auth._utils import warn_if_insecure
from sentinel_auth.authz import AuthzClient
from sentinel_auth.authz_middleware import AuthzMiddleware
from sentinel_auth.dependencies import get_current_user, get_request_auth_factory
from sentinel_auth.dependencies import require_action as _require_action
from sentinel_auth.middleware import JWTAuthMiddleware
from sentinel_auth.permissions import PermissionClient
from sentinel_auth.roles import RoleClient


class Sentinel:
    """One-line integration with the Sentinel identity service.

    Operates in two modes:

    **AuthZ mode** (default): Client apps authenticate users directly with
    their IdP. Sentinel validates the IdP token and issues an authorization-only
    JWT. The SDK middleware validates both tokens on each request.

    **Proxy mode**: Sentinel handles the entire OAuth flow and issues a single
    JWT containing both identity and authorization claims.

    Args:
        base_url: Root URL of the Sentinel identity service.
        service_name: The service name registered in Sentinel.
        service_key: Service API key (from admin panel).
        mode: ``"authz"`` (default) or ``"proxy"``.
        idp_public_key: PEM-encoded public key for validating IdP tokens.
            One of ``idp_public_key`` or ``idp_jwks_url`` is required when
            ``mode="authz"``.
        idp_jwks_url: JWKS endpoint URL for IdP token validation (e.g.
            ``https://www.googleapis.com/oauth2/v3/certs``).  Preferred
            over ``idp_public_key`` as it handles key rotation automatically.
        actions: Optional list of RBAC action dicts to register on startup.
        allowed_workspaces: Optional set of workspace IDs permitted to access
            this service. ``None`` allows all. Only used in proxy mode.
        cache_ttl: Seconds to cache ``accessible()`` and ``can()`` results
            in the ``PermissionClient``.  ``0`` (default) disables caching.
            Recommended: ``30``–``60`` for apps where permission changes are
            infrequent.  Write operations (share, unshare, visibility changes)
            automatically invalidate the cache.
    """

    def __init__(
        self,
        base_url: str,
        service_name: str,
        service_key: str,
        mode: str = "authz",
        idp_public_key: str | None = None,
        idp_jwks_url: str | None = None,
        actions: list[dict] | None = None,
        allowed_workspaces: set[str] | None = None,
        cache_ttl: float = 0,
    ):
        if not service_key:
            raise ValueError(
                "service_key is required. Create a service app in the Sentinel "
                "admin panel (/admin/service-apps) and pass the key here."
            )
        if mode not in ("authz", "proxy"):
            raise ValueError(f"mode must be 'authz' or 'proxy', got '{mode}'")
        if mode == "authz" and not idp_public_key and not idp_jwks_url:
            raise ValueError("idp_public_key or idp_jwks_url is required when mode='authz'")

        self.base_url = base_url.rstrip("/")
        warn_if_insecure(self.base_url, "Sentinel")
        self.service_name = service_name
        self.service_key = service_key
        self.mode = mode
        self.idp_public_key = idp_public_key
        self.idp_jwks_url = idp_jwks_url
        self.actions = actions
        self.allowed_workspaces = allowed_workspaces
        self.cache_ttl = cache_ttl

        self._permissions: PermissionClient | None = None
        self._roles: RoleClient | None = None
        self._authz: AuthzClient | None = None
        self._sentinel_public_key: str | None = None

    def __repr__(self) -> str:
        return f"Sentinel(base_url={self.base_url!r}, service_name={self.service_name!r})"

    @property
    def sentinel_public_key(self) -> str | None:
        """Sentinel's public key, fetched during lifespan startup."""
        return self._sentinel_public_key

    # -- Lazy clients --------------------------------------------------------

    @property
    def permissions(self) -> PermissionClient:
        """Lazily-created permission client."""
        if self._permissions is None:
            self._permissions = PermissionClient(
                base_url=self.base_url,
                service_name=self.service_name,
                service_key=self.service_key,
                cache_ttl=self.cache_ttl,
            )
        return self._permissions

    @property
    def roles(self) -> RoleClient:
        """Lazily-created role client."""
        if self._roles is None:
            self._roles = RoleClient(
                base_url=self.base_url,
                service_name=self.service_name,
                service_key=self.service_key,
            )
        return self._roles

    @property
    def authz(self) -> AuthzClient:
        """Lazily-created authz client."""
        if self._authz is None:
            self._authz = AuthzClient(self.base_url, self.service_key)
        return self._authz

    # -- Middleware -----------------------------------------------------------

    def protect(
        self,
        app: FastAPI,
        exclude_paths: list[str] | None = None,
    ) -> None:
        """Add authentication middleware to the app.

        In authz mode: adds ``AuthzMiddleware`` (validates IdP + authz tokens).
        In proxy mode: adds ``JWTAuthMiddleware`` (validates Sentinel JWT).

        In authz mode, the middleware reads keys lazily from this ``Sentinel``
        instance, so ``protect()`` can safely be called at module level before
        the lifespan fetches Sentinel's public key.
        """
        if self.mode == "authz":
            app.add_middleware(
                AuthzMiddleware,
                sentinel_instance=self,
                exclude_paths=exclude_paths,
            )
        else:
            app.add_middleware(
                JWTAuthMiddleware,
                base_url=self.base_url,
                exclude_paths=exclude_paths,
                allowed_workspaces=self.allowed_workspaces,
            )

    async def fetch_sentinel_public_key(self) -> str:
        """Fetch Sentinel's public key from its JWKS endpoint."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self.base_url}/.well-known/jwks.json")
            resp.raise_for_status()
            jwks = resp.json()
        if not jwks.get("keys"):
            raise RuntimeError("No keys found in Sentinel JWKS response")
        key_data = jwks["keys"][0]
        pub_key = RSAAlgorithm.from_jwk(key_data)
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
        )

        self._sentinel_public_key = pub_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
        return self._sentinel_public_key

    # -- Lifespan ------------------------------------------------------------

    @property
    def lifespan(self) -> Callable[[FastAPI], AsyncIterator[None]]:
        """Return an async context manager factory for ``FastAPI(lifespan=...)``.

        On startup:
        - In authz mode: fetches Sentinel's public key from JWKS endpoint.
        - Registers RBAC actions (if any were provided).
        On shutdown: closes HTTP clients.
        """

        @asynccontextmanager
        async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
            if self.mode == "authz":
                await self.fetch_sentinel_public_key()
            if self.actions:
                await self.roles.register_actions(self.actions)
            yield
            if self._permissions is not None:
                await self._permissions.close()
            if self._roles is not None:
                await self._roles.close()
            if self._authz is not None:
                await self._authz.close()

        return _lifespan

    # -- Dependency helpers --------------------------------------------------

    @property
    def require_user(self) -> Callable:
        """FastAPI dependency returning the authenticated user."""
        return get_current_user

    @property
    def get_auth(self) -> Callable:
        """FastAPI dependency returning a ``RequestAuth`` for the current request."""
        return get_request_auth_factory(
            permissions=self.permissions,
            roles=self.roles,
        )

    def require_action(self, action: str) -> Callable:
        """Dependency factory that enforces an RBAC action."""
        return _require_action(self.roles, action)
