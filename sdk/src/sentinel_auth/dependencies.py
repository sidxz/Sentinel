"""FastAPI dependency helpers for extracting auth context from requests."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

import httpx
from fastapi import Depends, HTTPException, Request

from sentinel_auth.auth import RequestAuth
from sentinel_auth.types import AuthenticatedUser, SentinelError, WorkspaceContext

if TYPE_CHECKING:
    from sentinel_auth.permissions import PermissionClient
    from sentinel_auth.roles import RoleClient


def get_token(request: Request) -> str:
    """Extract the bearer token from the Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return auth.removeprefix("Bearer ")


def get_current_user(request: Request) -> AuthenticatedUser:
    """Extract the authenticated user from request state (set by JWTAuthMiddleware)."""
    user: AuthenticatedUser | None = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def get_workspace_id(user: AuthenticatedUser = Depends(get_current_user)) -> uuid.UUID:
    """Extract the workspace ID from the current user's JWT context."""
    return user.workspace_id


def get_workspace_context(
    user: AuthenticatedUser = Depends(get_current_user),
) -> WorkspaceContext:
    """Extract full workspace context from the current user's JWT."""
    return WorkspaceContext(
        workspace_id=user.workspace_id,
        workspace_slug=user.workspace_slug,
        user_id=user.user_id,
        role=user.workspace_role,
    )


def require_role(minimum_role: str) -> Callable:
    """Dependency factory that enforces a minimum workspace role.

    Usage:
        @router.post("/things")
        async def create_thing(user: AuthenticatedUser = Depends(require_role("editor"))):
            ...
    """

    def dependency(
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if not user.has_role(minimum_role):
            raise HTTPException(
                status_code=403,
                detail=f"Requires at least '{minimum_role}' role, you have '{user.workspace_role}'",
            )
        return user

    return dependency


def require_action(role_client: RoleClient, action: str) -> Callable:
    """Dependency factory that enforces an RBAC action via the identity service.

    Usage:
        @router.get("/reports/export")
        async def export(user: AuthenticatedUser = Depends(require_action(roles, "reports:export"))):
            ...
    """

    async def dependency(request: Request, user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if not token:
            raise HTTPException(status_code=401, detail="Missing bearer token")
        try:
            allowed = await role_client.check_action(token, action, user.workspace_id)
        except (httpx.TransportError, httpx.TimeoutException):
            raise HTTPException(status_code=503, detail="Authorization service unavailable")
        except SentinelError as exc:
            raise HTTPException(status_code=exc.status_code or 502, detail="Authorization check failed")
        if not allowed:
            raise HTTPException(status_code=403, detail=f"Action '{action}' not permitted")
        return user

    return dependency


def get_request_auth_factory(
    permissions: PermissionClient | None = None,
    roles: RoleClient | None = None,
) -> Callable:
    """Create a FastAPI dependency that returns a ``RequestAuth`` per request.

    The returned dependency extracts the JWT token and authenticated user
    from the request and bundles them into a ``RequestAuth`` object with
    optional permission/role clients wired in.

    Args:
        permissions: Optional ``PermissionClient`` for entity-level checks.
        roles: Optional ``RoleClient`` for RBAC action checks.

    Returns:
        A FastAPI-compatible dependency function.
    """

    def dependency(
        request: Request,
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> RequestAuth:
        token: str | None = getattr(request.state, "token", None)
        if token is None:
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing bearer token")
            token = auth.removeprefix("Bearer ")
        return RequestAuth(user=user, _token=token, _permissions=permissions, _roles=roles)

    return dependency
