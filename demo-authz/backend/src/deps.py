"""Convenience dependencies for the authz demo app."""

from fastapi import Request

from sentinel_auth.dependencies import (  # noqa: F401
    get_current_user,
    get_workspace_context,
    get_workspace_id,
    require_role,
)
from sentinel_auth.types import AuthenticatedUser, WorkspaceContext  # noqa: F401


def get_token(request: Request) -> str:
    """Extract the authz token set by AuthzMiddleware."""
    return request.state.token
