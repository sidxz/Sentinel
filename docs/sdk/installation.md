# Installation

## Install from PyPI

Using [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv add sentinel-auth-sdk
```

Using pip:

```bash
pip install sentinel-auth-sdk
```

This installs the SDK and all its dependencies (`pyjwt[crypto]`, `httpx`, `cryptography`, `pydantic`, `starlette`, `fastapi`).

## Editable Install for Local Development

If you are developing against a local checkout of the Sentinel monorepo, you can install the SDK in editable mode so changes to the SDK source are reflected immediately.

Add the SDK as a dependency in your service's `pyproject.toml`:

```toml
[project]
dependencies = [
    "sentinel-auth-sdk",
]
```

Then configure uv to resolve it from the local path by adding a `[tool.uv.sources]` entry:

```toml
[tool.uv.sources]
sentinel-auth-sdk = { path = "../sentinel/sdk", editable = true }
```

Run `uv sync` to install:

```bash
uv sync
```

The SDK will be installed as an editable link. Any changes you make to the SDK code under `sentinel/sdk/src/sentinel_auth/` will be picked up without reinstalling.

## Verify Installation

Confirm the SDK is installed and importable:

```python
>>> from sentinel_auth.types import AuthenticatedUser, WorkspaceContext
>>> from sentinel_auth.middleware import JWTAuthMiddleware
>>> from sentinel_auth.dependencies import get_current_user
>>> from sentinel_auth.permissions import PermissionClient
```

## Token Verification Setup

The SDK's JWT middleware needs to verify token signatures from Sentinel. There are two approaches:

### JWKS Auto-Discovery (recommended)

Point the middleware at Sentinel's JWKS endpoint. The signing key is fetched lazily on first request and cached. No key files to distribute or rotate.

```python
app.add_middleware(
    JWTAuthMiddleware,
    base_url="http://sentinel:9003",
)
```

The [`Sentinel` autoconfig class](autoconfig.md) does this automatically — it derives the JWKS URL from `base_url`:

```python
sentinel = Sentinel(
    base_url="http://sentinel:9003",
    service_name="my-service",
    service_key="sk_...",
)
sentinel.protect(app)  # adds JWTAuthMiddleware with JWKS
```

### PEM Public Key (alternative)

If your deployment cannot reach Sentinel at runtime (air-gapped, pre-baked images), you can provide the RSA public key directly.

<details>
<summary>PEM key distribution options</summary>

**File on disk:**

```bash
cp /path/to/sentinel/keys/public.pem ./keys/public.pem
```

```python
from pathlib import Path

PUBLIC_KEY = Path("keys/public.pem").read_text()
app.add_middleware(JWTAuthMiddleware, public_key=PUBLIC_KEY)
```

**Environment variable** (useful for containers):

```bash
export SENTINEL_PUBLIC_KEY="$(cat keys/public.pem)"
```

```python
import os

PUBLIC_KEY = os.environ["SENTINEL_PUBLIC_KEY"]
app.add_middleware(JWTAuthMiddleware, public_key=PUBLIC_KEY)
```

**Shared Docker volume:**

```yaml
services:
  my-service:
    volumes:
      - sentinel-keys:/app/keys:ro

  sentinel:
    volumes:
      - sentinel-keys:/app/keys

volumes:
  sentinel-keys:
```

</details>

## Requirements

- **Python** >= 3.12
- **Sentinel** running and accessible over the network (for JWKS, permission, and role API calls)

## Next Steps

- [Middleware](middleware.md) -- configure the JWT validation middleware
- [Integration Guide](integration.md) -- full walkthrough of adding auth to your service
