"""Sentinel autoconfig — single entry point for integrating FastAPI apps."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from sentinel_auth._utils import warn_if_insecure
from sentinel_auth.dependencies import get_current_user, get_request_auth_factory
from sentinel_auth.dependencies import require_action as _require_action
from sentinel_auth.middleware import JWTAuthMiddleware
from sentinel_auth.permissions import PermissionClient
from sentinel_auth.roles import RoleClient


class Sentinel:
    """One-line integration with the Sentinel identity service.

    Replaces the typical ~30 lines of boilerplate (construct JWKS URL,
    create ``PermissionClient``, create ``RoleClient``, write a lifespan,
    wire middleware) with a single object::

        sentinel = Sentinel(
            base_url="http://localhost:9003",
            service_name="my-service",
            service_key="sk_...",
            actions=[
                {"action": "reports:export", "description": "Export reports"},
            ],
        )
        app = FastAPI(lifespan=sentinel.lifespan)
        sentinel.protect(app)

    Args:
        base_url: Root URL of the Sentinel identity service.
        service_name: The service name registered in Sentinel.
        service_key: Service API key (from admin panel). Must be non-empty.
        actions: Optional list of RBAC action dicts to register on startup.
            Each dict should have ``action`` (str) and optionally
            ``description`` (str).
        allowed_workspaces: Optional set of workspace IDs (as strings)
            permitted to access this service.  ``None`` allows all.
    """

    def __init__(
        self,
        base_url: str,
        service_name: str,
        service_key: str,
        actions: list[dict] | None = None,
        allowed_workspaces: set[str] | None = None,
    ):
        if not service_key:
            raise ValueError(
                "service_key is required. Create a service app in the Sentinel "
                "admin panel (/admin/service-apps) and pass the key here."
            )

        self.base_url = base_url.rstrip("/")
        self.service_name = service_name
        self.service_key = service_key
        self.actions = actions
        self.allowed_workspaces = allowed_workspaces

        self._permissions: PermissionClient | None = None
        self._roles: RoleClient | None = None

        warn_if_insecure(self.base_url, "Sentinel")

    # -- Lazy clients --------------------------------------------------------

    @property
    def permissions(self) -> PermissionClient:
        """Lazily-created permission client."""
        if self._permissions is None:
            self._permissions = PermissionClient(
                base_url=self.base_url,
                service_name=self.service_name,
                service_key=self.service_key,
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

    # -- Middleware -----------------------------------------------------------

    def protect(
        self,
        app: FastAPI,
        exclude_paths: list[str] | None = None,
    ) -> None:
        """Add ``JWTAuthMiddleware`` to the app.

        The JWKS URL is auto-derived from ``base_url``.

        Args:
            app: The FastAPI application instance.
            exclude_paths: Path prefixes that skip JWT validation
                (defaults to ``["/health", "/docs", "/openapi.json"]``).
        """
        app.add_middleware(
            JWTAuthMiddleware,
            base_url=self.base_url,
            exclude_paths=exclude_paths,
            allowed_workspaces=self.allowed_workspaces,
        )

    # -- Lifespan ------------------------------------------------------------

    @property
    def lifespan(self) -> Callable[[FastAPI], AsyncIterator[None]]:
        """Return an async context manager factory for ``FastAPI(lifespan=...)``.

        On startup: registers RBAC actions (if any were provided).
        On shutdown: closes the HTTP clients.
        """

        @asynccontextmanager
        async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
            if self.actions:
                await self.roles.register_actions(self.actions)
            yield
            if self._permissions is not None:
                await self._permissions.close()
            if self._roles is not None:
                await self._roles.close()

        return _lifespan

    # -- Dependency helpers --------------------------------------------------

    @property
    def require_user(self) -> Callable:
        """FastAPI dependency returning the authenticated user.

        Usage::

            @app.get("/items")
            async def list_items(user: AuthenticatedUser = Depends(sentinel.require_user)):
                ...
        """
        return get_current_user

    @property
    def get_auth(self) -> Callable:
        """FastAPI dependency returning a ``RequestAuth`` for the current request.

        The ``RequestAuth`` bundles the authenticated user with token-backed
        authorization methods (``can``, ``check_action``, ``accessible``),
        eliminating the need to manually extract and pass JWT tokens.

        Usage::

            @app.post("/artifacts")
            async def create(auth: RequestAuth = Depends(sentinel.get_auth)):
                if await auth.can("artifact", artifact_id, "edit"):
                    ...
        """
        return get_request_auth_factory(
            permissions=self.permissions,
            roles=self.roles,
        )

    def require_action(self, action: str) -> Callable:
        """Dependency factory that enforces an RBAC action.

        Usage::

            @router.get("/reports/export")
            async def export(
                user: AuthenticatedUser = Depends(sentinel.require_action("reports:export")),
            ):
                ...
        """
        return _require_action(self.roles, action)
