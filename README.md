# Daikon Identity Service

Authentication, workspace management, and entity-level permissions as a reusable microservice.

Users always come from external identity providers (Google, GitHub, Microsoft EntraID, or any OIDC-compliant SSO). The service stores a local user record synced from the IdP on login, and manages workspaces, groups, and resource permissions.

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Docker & Docker Compose

### 1. Clone and install

```bash
cd identity-service
uv sync
```

### 2. Generate JWT signing keys

```bash
mkdir -p keys
openssl genrsa -out keys/private.pem 2048
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your OAuth provider credentials
```

### 4. Start infrastructure

```bash
# Create the shared network (if it doesn't exist)
docker network create docu_store-network 2>/dev/null || true

# Start PostgreSQL + Redis
docker compose up -d identity-postgres identity-redis
```

### 5. Run database migrations

```bash
cd service
uv run alembic revision --autogenerate -m "initial"
uv run alembic upgrade head
cd ..
```

### 6. Start the service

```bash
cd service
uv run uvicorn src.main:app --host 0.0.0.0 --port 9003 --reload
```

The API is now available at http://localhost:9003. Interactive docs at http://localhost:9003/docs.

## Project Structure

```
identity-service/
├── service/                # FastAPI microservice
│   ├── src/
│   │   ├── main.py         # App entrypoint
│   │   ├── config.py       # Pydantic settings
│   │   ├── database.py     # SQLAlchemy async engine
│   │   ├── models/         # SQLAlchemy ORM models (8 tables)
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── services/       # Business logic layer
│   │   ├── auth/           # OAuth2 providers + JWT
│   │   └── api/            # FastAPI route handlers
│   ├── migrations/         # Alembic migrations
│   └── Dockerfile
├── sdk/                    # Pip-installable SDK
│   └── src/identity_sdk/
│       ├── types.py        # AuthenticatedUser, WorkspaceContext
│       ├── middleware.py   # JWTAuthMiddleware
│       ├── dependencies.py # FastAPI deps (get_current_user, require_role, require_action)
│       ├── permissions.py  # PermissionClient (entity ACL HTTP client)
│       └── roles.py        # RoleClient (RBAC HTTP client)
├── demo/                   # Demo app for testing
├── docs/                   # Design documents
│   └── PLAN.md
├── docker-compose.yml
└── .env.example
```

## API Overview

| Group | Endpoints | Description |
|-------|-----------|-------------|
| **Auth** | `GET /auth/login/{provider}`, `GET /auth/callback/{provider}`, `POST /auth/refresh`, `POST /auth/logout` | OAuth2/OIDC login flow |
| **Users** | `GET /users/me`, `PATCH /users/me` | Current user profile |
| **Workspaces** | `POST /workspaces`, `GET /workspaces`, `GET/PATCH/DELETE /workspaces/{id}` | Workspace CRUD |
| **Members** | `GET /workspaces/{id}/members`, `POST .../invite`, `PATCH/DELETE .../members/{uid}` | Membership management |
| **Groups** | `POST/GET /workspaces/{id}/groups`, `PATCH/DELETE .../groups/{gid}`, member add/remove | Group management |
| **Permissions** | `POST /permissions/check`, `POST /permissions/register`, share/revoke, get ACL | Entity-level ACLs |
| **Roles (RBAC)** | `POST /roles/actions/register`, `POST /roles/check-action`, `GET /roles/user-actions` | Action-based authorization |

Full interactive docs available at `/docs` when the service is running.

## SDK Usage

Install the SDK in your consuming app:

```bash
# Development (editable install)
uv add --editable /path/to/identity-service/sdk

# Or add to pyproject.toml
# dependencies = ["daikon-identity-sdk"]
```

### Add JWT middleware to your FastAPI app

```python
from fastapi import FastAPI
from identity_sdk.middleware import JWTAuthMiddleware

app = FastAPI()
public_key = open("path/to/public.pem").read()
app.add_middleware(JWTAuthMiddleware, public_key=public_key)
```

### Use dependency injection in routes

```python
from fastapi import Depends
from identity_sdk.dependencies import get_current_user, require_role, get_workspace_id
from identity_sdk.types import AuthenticatedUser

@router.get("/my-things")
async def list_things(user: AuthenticatedUser = Depends(get_current_user)):
    # user.user_id, user.workspace_id, user.workspace_role, user.groups
    return await fetch_things(workspace_id=user.workspace_id)

@router.post("/my-things")
async def create_thing(user: AuthenticatedUser = Depends(require_role("editor"))):
    # Only editors, admins, and owners can reach this
    ...
```

### Check entity-level permissions

```python
from identity_sdk.permissions import PermissionClient

perm_client = PermissionClient(
    base_url="http://localhost:9003",
    service_name="my-app",
)

# Check if user can edit a specific resource
allowed = await perm_client.can(
    token=user_jwt,
    resource_type="document",
    resource_id=doc_id,
    action="edit",
)

# Register a new resource when created
await perm_client.register_resource(
    token=user_jwt,
    resource_type="document",
    resource_id=new_doc_id,
    workspace_id=workspace_id,
    owner_id=user_id,
)
```

### Check action-based permissions (RBAC)

```python
from identity_sdk.roles import RoleClient
from identity_sdk.dependencies import require_action

role_client = RoleClient(
    base_url="http://localhost:9003",
    service_name="my-app",
    service_key="sk_your_service_key",
)

# Register actions on startup
await role_client.register_actions([
    {"action": "reports:export", "description": "Export reports"},
])

# Use as a dependency
@router.get("/reports/export")
async def export(user = Depends(require_action(role_client, "reports:export"))):
    ...
```

## OAuth2 Provider Setup

### Google

1. Go to Google Cloud Console > APIs & Services > Credentials
2. Create an OAuth 2.0 Client ID (Web application)
3. Set redirect URI: `http://localhost:9003/auth/callback/google`
4. Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to `.env`

### GitHub

1. Go to GitHub > Settings > Developer Settings > OAuth Apps
2. Create a new OAuth App
3. Set callback URL: `http://localhost:9003/auth/callback/github`
4. Add `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` to `.env`

### Microsoft EntraID

1. Go to Azure Portal > App registrations
2. Register a new application
3. Set redirect URI: `http://localhost:9003/auth/callback/entra_id`
4. Add `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET`, and `ENTRA_TENANT_ID` to `.env`

## Authorization Model

**Three-tier system:**

1. **Workspace roles** (from JWT, no service call): `viewer` < `editor` < `admin` < `owner`
2. **Custom roles / RBAC** (via role service): service-scoped actions organized into workspace roles (e.g., "can user export reports?")
3. **Entity ACLs** (via permission service): per-resource visibility (`private`/`workspace`) + sharing grants

**Entity ACL resolution order:** workspace member? -> entity owner? -> workspace admin? -> workspace-visible? -> user share? -> group share? -> deny.

## Architecture

For the full design document including data model, JWT structure, and integration plan, see [docs/PLAN.md](docs/PLAN.md).
