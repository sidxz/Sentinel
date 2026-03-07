# SDK Reference

This section contains API reference documentation for the `sentinel-auth-sdk` Python package, auto-generated from source code docstrings using [mkdocstrings](https://mkdocstrings.github.io/).

Each page corresponds to a module in the `sentinel_auth` package:

| Module | Description |
|--------|-------------|
| [Types](types.md) | Data classes (`AuthenticatedUser`, `WorkspaceContext`) and `SentinelError` exception used throughout the SDK |
| [Middleware](middleware.md) | `JWTAuthMiddleware` for validating tokens on incoming requests |
| [Dependencies](dependencies.md) | FastAPI dependency functions for injecting user/workspace context |
| [Permissions](permissions.md) | `PermissionClient` for interacting with the permissions API |
| [Roles](roles.md) | `RoleClient` for RBAC action registration and checks |
| [Autoconfig](autoconfig.md) | `Sentinel` class for one-line FastAPI integration (middleware, lifespan, clients) |

## Usage

Install the SDK in your service:

```bash
uv add sentinel-auth-sdk
```

Then import what you need:

```python
from sentinel_auth.types import AuthenticatedUser, SentinelError
from sentinel_auth.middleware import JWTAuthMiddleware
from sentinel_auth.dependencies import get_current_user, get_workspace_id
from sentinel_auth.permissions import PermissionClient
from sentinel_auth.roles import RoleClient
from sentinel_auth.sentinel import Sentinel
```

!!! note "Docstring format"
    All docstrings follow Google style. Parameters, return types, and raised exceptions are documented inline in the source and rendered here automatically.
