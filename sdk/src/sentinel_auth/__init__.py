from importlib.metadata import version

from sentinel_auth.auth import RequestAuth
from sentinel_auth.dependencies import get_token
from sentinel_auth.middleware import JWTAuthMiddleware
from sentinel_auth.permissions import PermissionClient
from sentinel_auth.roles import RoleClient
from sentinel_auth.sentinel import Sentinel
from sentinel_auth.types import AuthenticatedUser, SentinelError, WorkspaceContext

__version__ = version("sentinel-auth-sdk")
__all__ = [
    "AuthenticatedUser",
    "JWTAuthMiddleware",
    "PermissionClient",
    "RequestAuth",
    "RoleClient",
    "Sentinel",
    "SentinelError",
    "WorkspaceContext",
    "__version__",
    "get_token",
]
