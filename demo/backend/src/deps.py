"""Convenience dependencies for the demo app."""

from fastapi import Request

from identity_sdk.dependencies import (  # noqa: F401
    get_current_user,
    get_workspace_context,
    get_workspace_id,
    require_role,
)
from identity_sdk.permissions import PermissionClient
from identity_sdk.roles import RoleClient
from identity_sdk.types import AuthenticatedUser, WorkspaceContext  # noqa: F401


def get_token(request: Request) -> str:
    """Extract raw JWT from the Authorization header."""
    return request.headers["Authorization"].removeprefix("Bearer ")


def get_permissions(request: Request) -> PermissionClient:
    return request.app.state.permissions


def get_roles(request: Request) -> RoleClient:
    return request.app.state.roles
