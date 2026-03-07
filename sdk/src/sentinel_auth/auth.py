"""Request-scoped auth context that bundles identity with authorization capabilities.

``RequestAuth`` is created once per request by the framework layer (e.g. a FastAPI
dependency) and can be passed to any layer — including DDD use cases — as a plain
Python object.  Receivers only need to define a ``Protocol`` matching the
attributes/methods they use; no SDK import required.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sentinel_auth.types import AuthenticatedUser, SentinelError

if TYPE_CHECKING:
    from sentinel_auth.permissions import PermissionClient
    from sentinel_auth.roles import RoleClient


@dataclass
class RequestAuth:
    """Per-request auth context combining user identity with token-backed authorization.

    The raw JWT token is stored privately and never exposed in ``repr``.
    Authorization methods (``can``, ``check_action``, ``accessible``) use it
    internally when calling Sentinel APIs.

    Attributes:
        user: The authenticated user from JWT claims.
    """

    user: AuthenticatedUser
    _token: str = field(repr=False)
    _permissions: PermissionClient | None = field(default=None, repr=False, compare=False)
    _roles: RoleClient | None = field(default=None, repr=False, compare=False)

    # -- Forwarded identity properties -----------------------------------------

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.user_id

    @property
    def workspace_id(self) -> uuid.UUID:
        return self.user.workspace_id

    @property
    def workspace_role(self) -> str:
        return self.user.workspace_role

    @property
    def email(self) -> str:
        return self.user.email

    @property
    def name(self) -> str:
        return self.user.name

    @property
    def groups(self) -> list[uuid.UUID]:
        return self.user.groups

    @property
    def is_admin(self) -> bool:
        return self.user.is_admin

    @property
    def is_editor(self) -> bool:
        return self.user.is_editor

    def has_role(self, minimum_role: str) -> bool:
        """Check workspace role hierarchy. No network call."""
        return self.user.has_role(minimum_role)

    # -- Authorization (token hidden internally) -------------------------------

    async def can(
        self,
        resource_type: str,
        resource_id: uuid.UUID,
        action: str,
    ) -> bool:
        """Check entity-level permission via Sentinel's Zanzibar API."""
        if self._permissions is None:
            raise SentinelError("PermissionClient not configured on this RequestAuth")
        return await self._permissions.can(self._token, resource_type, resource_id, action)

    async def check_action(self, action: str) -> bool:
        """Check RBAC action via Sentinel's role API."""
        if self._roles is None:
            raise SentinelError("RoleClient not configured on this RequestAuth")
        return await self._roles.check_action(self._token, action, self.user.workspace_id)

    async def accessible(
        self,
        resource_type: str,
        action: str,
        limit: int | None = None,
    ) -> tuple[list[uuid.UUID], bool]:
        """Get accessible resource IDs for list filtering.

        Returns ``(resource_ids, has_full_access)``.
        """
        if self._permissions is None:
            raise SentinelError("PermissionClient not configured on this RequestAuth")
        return await self._permissions.accessible(
            self._token,
            resource_type,
            action,
            self.user.workspace_id,
            limit,
        )

    async def register_resource(
        self,
        resource_type: str,
        resource_id: uuid.UUID,
        visibility: str = "workspace",
    ) -> dict:
        """Register a new resource ACL (uses service key + user context)."""
        if self._permissions is None:
            raise SentinelError("PermissionClient not configured on this RequestAuth")
        return await self._permissions.register_resource(
            resource_type=resource_type,
            resource_id=resource_id,
            workspace_id=self.user.workspace_id,
            owner_id=self.user.user_id,
            visibility=visibility,
        )
