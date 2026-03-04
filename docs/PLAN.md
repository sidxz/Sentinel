# Identity, Workspace & Permissions — Backend Plan

## Context

docu-store currently has **zero auth, zero workspace isolation, zero permissions**. All data is globally accessible. The frontend has workspace-aware routing (`/[workspace]/...`) but it's stubbed — hardcoded to "default" workspace with a mock user.

**Goal**: Build a separate **identity microservice** that handles authentication (SSO/Google/GitHub/EntraID via OAuth2/OIDC), workspace management, groups, and entity-level permissions. Then integrate it into docu-store's backend via a thin SDK. The service must be **reusable across other apps**.

---

## Architecture Overview

```
┌─────────────────┐     JWT      ┌──────────────────┐
│  Frontend (FE)  │─────────────→│  docu-store BE   │
│  Next.js        │              │  (FastAPI)       │
└────────┬────────┘              └────────┬─────────┘
         │                                │
         │  OAuth2 flow                   │  identity-sdk
         │  + JWT                         │  (JWT validation +
         ▼                                │   permission checks)
┌─────────────────┐                       │
│ Identity Service │◄──────────────────────┘
│ (FastAPI)        │
│                  │
│ PostgreSQL       │
│ Redis (cache)    │
└──────────────────┘
```

**Three deliverables:**
1. **`identity-service/`** — Standalone FastAPI microservice in its own git repo (own DB, own Docker container, reusable across projects)
2. **`identity-service/sdk/`** — Thin Python SDK inside the identity-service repo (JWT middleware, deps, permission client). Pip-installable, consumed by docu-store and other apps.
3. **docu-store integration** — Wire workspace_id + owner_id through aggregates, read models, vector stores, and API routes

---

## Design Decisions

### D1: Why Authlib over python-social-auth?
- **Authlib** is the modern, async-native OAuth2/OIDC library for Python
- First-class Starlette/FastAPI integration (`authlib.integrations.starlette`)
- Supports Google, GitHub, Microsoft EntraID, and **any generic OIDC provider** (covers SSO requirement)
- python-social-auth is Django-centric and lacks async support
- Authlib handles the full OIDC flow: discovery, token exchange, ID token validation, userinfo

### D2: Why PostgreSQL for the identity service?
- Users, workspaces, memberships, groups are inherently **relational** data
- Need ACID transactions (e.g., invite user + create membership atomically)
- JOINs needed for permission resolution (user → memberships → groups → shares)
- SQLAlchemy 2.0 async + asyncpg gives us type-safe, performant queries
- No benefit to event-sourcing here — identity data is CRUD, not event-driven

### D3: Soft isolation with workspace_id filtering
- All existing shared collections (MongoDB, Qdrant, EventStoreDB) remain shared
- Every document/point/event gets a `workspace_id` field
- Every query includes a `workspace_id` filter condition
- Simpler ops, no per-workspace provisioning
- Workspace_id is **set at creation time** and **immutable** — baked into the aggregate

### D4: JWT-based stateless auth (with Redis blacklist)
- Access token: **short-lived** (15 min), contains user_id, workspace_id, workspace_role, group_ids
- Refresh token: **long-lived** (7 days), stored in Redis with revocation support
- docu-store validates JWTs **locally** using the identity service's public key (no cross-service call for auth)
- Only entity-level ACL checks require calling the identity service (and can be cached)

### D5: Workspace roles + entity ACLs (two-tier permission model)

**Tier 1 — Workspace roles** (checked from JWT, no service call):
| Role | Can view all | Can create | Can edit own | Can edit all | Can manage members |
|------|-------------|-----------|-------------|-------------|-------------------|
| Viewer | yes | no | no | no | no |
| Editor | yes | yes | yes | no | no |
| Admin | yes | yes | yes | yes | yes |
| Owner | yes | yes | yes | yes | yes (+ delete workspace) |

**Tier 2 — Entity ACLs** (checked via identity service, cached):
- Every entity has an `owner_id` (creator) and `visibility` (private | workspace)
- **Private entities**: only owner + explicitly shared users/groups can access
- **Workspace-visible entities** (default): all workspace members can view, workspace role governs edit
- Sharing grants specific permissions (`view` | `edit`) to specific users or groups

**Permission resolution order:**
1. Must be workspace member → deny if not
2. Is entity owner? → full access
3. Is workspace admin/owner? → full access
4. Is entity workspace-visible? → apply workspace role
5. Check direct user shares → grant if found
6. Check group shares → grant if found
7. Default: deny

### D6: Generic resource permission model (reusable)
The identity service stores permissions generically — it doesn't know what an "artifact" is:
```
Resource:
  service_name: "docu-store"     # which app registered this
  resource_type: "artifact"      # app-defined entity type
  resource_id: UUID              # entity ID
  workspace_id: UUID
  owner_id: UUID
  visibility: "private" | "workspace"
```
Any app can register resources and check permissions using the same API.

### D7: OAuth2/OIDC provider support
Using Authlib's OIDC client, we support:
- **Google** — OAuth2 + OpenID Connect
- **GitHub** — OAuth2 (+ userinfo endpoint, GitHub doesn't do full OIDC)
- **Microsoft EntraID** — OAuth2 + OIDC (covers enterprise SSO)
- **Any OIDC-compliant IdP** — generic OIDC provider config (Okta, Auth0, Keycloak, etc.)

Providers are configured in the identity service's settings. Users from different orgs/providers can coexist in the same workspace.

### D8: No local user management
Users are **never** created directly. They always come from external identity providers (enterprise SSO like EntraID, or social logins like Google/GitHub). The external IdP handles MFA, password policies, account recovery, etc. The identity service only stores a local user record (email, name, avatar) synced from the IdP on login.

---

## Data Model (Identity Service — PostgreSQL)

```sql
-- Core identity (synced from external IdPs on login)
users (
  id            UUID PRIMARY KEY,
  email         TEXT UNIQUE NOT NULL,
  name          TEXT NOT NULL,
  avatar_url    TEXT,
  is_active     BOOLEAN DEFAULT TRUE,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
)

-- OAuth2/OIDC linked accounts
social_accounts (
  id                UUID PRIMARY KEY,
  user_id           UUID REFERENCES users(id) ON DELETE CASCADE,
  provider          TEXT NOT NULL,           -- 'google', 'github', 'entra_id', 'oidc'
  provider_user_id  TEXT NOT NULL,
  provider_data     JSONB,                  -- raw provider profile
  UNIQUE(provider, provider_user_id)
)

-- Workspaces
workspaces (
  id          UUID PRIMARY KEY,
  slug        TEXT UNIQUE NOT NULL,          -- URL-friendly identifier
  name        TEXT NOT NULL,
  description TEXT,
  created_by  UUID REFERENCES users(id),
  created_at  TIMESTAMPTZ DEFAULT NOW()
)

-- Workspace membership (user <-> workspace with role)
workspace_memberships (
  id            UUID PRIMARY KEY,
  workspace_id  UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id       UUID REFERENCES users(id) ON DELETE CASCADE,
  role          TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'editor', 'viewer')),
  joined_at     TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(workspace_id, user_id)
)

-- Groups within a workspace
groups (
  id            UUID PRIMARY KEY,
  workspace_id  UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  description   TEXT,
  created_by    UUID REFERENCES users(id),
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(workspace_id, name)
)

-- Group membership
group_memberships (
  id        UUID PRIMARY KEY,
  group_id  UUID REFERENCES groups(id) ON DELETE CASCADE,
  user_id   UUID REFERENCES users(id) ON DELETE CASCADE,
  added_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(group_id, user_id)
)

-- Generic resource permissions (entity ACLs)
resource_permissions (
  id              UUID PRIMARY KEY,
  service_name    TEXT NOT NULL,             -- 'docu-store', 'cage-fusion', etc.
  resource_type   TEXT NOT NULL,             -- 'artifact', 'page', etc.
  resource_id     UUID NOT NULL,
  workspace_id    UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  owner_id        UUID REFERENCES users(id),
  visibility      TEXT NOT NULL DEFAULT 'workspace' CHECK (visibility IN ('private', 'workspace')),
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(service_name, resource_type, resource_id)
)

-- Sharing grants on resources
resource_shares (
  id                      UUID PRIMARY KEY,
  resource_permission_id  UUID REFERENCES resource_permissions(id) ON DELETE CASCADE,
  grantee_type            TEXT NOT NULL CHECK (grantee_type IN ('user', 'group')),
  grantee_id              UUID NOT NULL,
  permission              TEXT NOT NULL CHECK (permission IN ('view', 'edit')),
  granted_by              UUID REFERENCES users(id),
  granted_at              TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(resource_permission_id, grantee_type, grantee_id)
)
```

---

## Identity Service API

### Auth endpoints
```
GET  /auth/login/{provider}          -> Redirect to OAuth2 provider
GET  /auth/callback/{provider}       -> Handle OAuth2 callback, issue JWT
POST /auth/refresh                   -> Refresh access token
POST /auth/logout                    -> Revoke refresh token
GET  /auth/providers                 -> List configured providers
```

### User endpoints
```
GET   /users/me                      -> Current user profile
PATCH /users/me                      -> Update profile
```

### Workspace endpoints
```
POST   /workspaces                   -> Create workspace
GET    /workspaces                   -> List user's workspaces
GET    /workspaces/{id}              -> Get workspace details
PATCH  /workspaces/{id}              -> Update workspace
DELETE /workspaces/{id}              -> Delete workspace (owner only)
```

### Membership endpoints
```
GET    /workspaces/{id}/members              -> List members
POST   /workspaces/{id}/members/invite       -> Invite user (by email)
PATCH  /workspaces/{id}/members/{user_id}    -> Change role
DELETE /workspaces/{id}/members/{user_id}    -> Remove member
```

### Group endpoints
```
POST   /workspaces/{id}/groups               -> Create group
GET    /workspaces/{id}/groups               -> List groups
PATCH  /workspaces/{id}/groups/{group_id}    -> Update group
DELETE /workspaces/{id}/groups/{group_id}    -> Delete group
POST   /workspaces/{id}/groups/{gid}/members/{uid}    -> Add member to group
DELETE /workspaces/{id}/groups/{gid}/members/{uid}    -> Remove from group
```

### Permission endpoints (called by integrating apps)
```
POST /permissions/check              -> Check access (batch: [{service, type, id, action}])
POST /permissions/register           -> Register resource + owner
PATCH /permissions/{id}/visibility   -> Change visibility (private/workspace)
POST /permissions/{id}/share         -> Grant access to user/group
DELETE /permissions/{id}/share       -> Revoke access
GET  /permissions/resource/{service}/{type}/{id}  -> Get resource ACL
```

---

## JWT Structure

```json
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "name": "User Name",
  "wid": "workspace-uuid",
  "wslug": "my-workspace",
  "wrole": "editor",
  "groups": ["group-uuid-1", "group-uuid-2"],
  "iat": 1709568000,
  "exp": 1709568900
}
```

Short claims (`wid`, `wslug`, `wrole`) keep token size small. The workspace context is set when the user **selects a workspace** after login (workspace switcher in FE).

---

## Identity SDK (sdk/)

A thin pip-installable package that apps import:

```python
# FastAPI middleware -- validates JWT, sets request state
from identity_sdk.middleware import JWTAuthMiddleware

# FastAPI dependencies -- extract user/workspace from request
from identity_sdk.dependencies import (
    get_current_user,      # -> AuthenticatedUser
    get_workspace_id,      # -> UUID
    require_role,          # -> dependency factory: require_role("editor")
)

# Permission client -- calls identity service for ACL checks
from identity_sdk.permissions import PermissionClient

# Types
from identity_sdk.types import AuthenticatedUser, WorkspaceContext
```

**Key types:**
```python
@dataclass
class AuthenticatedUser:
    user_id: UUID
    email: str
    name: str
    workspace_id: UUID
    workspace_slug: str
    workspace_role: str          # 'owner' | 'admin' | 'editor' | 'viewer'
    groups: list[UUID]

@dataclass
class WorkspaceContext:
    workspace_id: UUID
    workspace_slug: str
    user_id: UUID
    role: str
```

---

## docu-store Integration Changes

### 1. Aggregates — add workspace_id + owner_id

Both `Artifact` and `Page` aggregates get `workspace_id: UUID` and `owner_id: UUID` as creation-time properties. These are set via the `Created` event and are **immutable**.

**Files:**
- `domain/aggregates/artifact.py` — add to `create()`, `Created` event, `__init__`
- `domain/aggregates/page.py` — add to `create()`, `Created` event, `__init__`

### 2. Read model projectors — project workspace_id + owner_id

The event projectors extract `workspace_id` and `owner_id` from `Created` events and store them in MongoDB documents.

**Files:**
- `infrastructure/event_projectors/page_projector.py`
- `infrastructure/event_projectors/artifact_projector.py`

### 3. MongoDB read repository — filter by workspace_id

All queries (`list_artifacts`, `get_artifact_by_id`, etc.) receive `workspace_id` and add it to the MongoDB filter.

**Files:**
- `infrastructure/read_repositories/mongo_read_repository.py`
- `application/ports/repositories/artifact_read_models.py` (add workspace_id param)
- `application/ports/repositories/page_read_models.py` (add workspace_id param)

### 4. Qdrant vector stores — add workspace_id to payloads and filters

All upsert operations include `workspace_id` in the payload. All search operations include a `workspace_id` filter condition.

**Files:**
- `infrastructure/vector_stores/qdrant_store.py`
- `infrastructure/vector_stores/compound_qdrant_store.py`
- `infrastructure/vector_stores/summary_qdrant_store.py`
- `application/ports/vector_store.py` (add workspace_id param)
- `application/ports/compound_vector_store.py`
- `application/ports/summary_vector_store.py`

### 5. API routes — inject auth context

All route handlers get `current_user: AuthenticatedUser` via FastAPI dependency injection. The workspace_id comes from the JWT (not from the URL path — the URL slug is for frontend routing only).

**Files:**
- `interfaces/api/routes/artifact_routes.py`
- `interfaces/api/routes/page_routes.py`
- `interfaces/api/routes/search_routes.py`
- `interfaces/dependencies.py` (add identity SDK dependencies)

### 6. Use cases — receive workspace context

Create use cases receive `workspace_id` and `owner_id`. Read use cases receive `workspace_id` for filtering. The use case validates that the loaded aggregate belongs to the requesting workspace.

### 7. Pipeline worker + read worker — workspace context flows through events

The pipeline worker and read worker don't need auth — they process events that already contain `workspace_id` (baked into the aggregate at creation time). No changes needed for auth; the workspace_id is already in the event payload.

### 8. Register resources with identity service

When an artifact/page is created, the use case calls the identity service (via the SDK's `PermissionClient`) to register the resource permission. This is async (fire-and-forget via Temporal or background task).

---

## Library Stack

### Identity Service
| Library | Purpose |
|---------|---------|
| **FastAPI** | Web framework (consistent with docu-store) |
| **Authlib** | OAuth2/OIDC client (Google, GitHub, EntraID, generic OIDC) |
| **PyJWT** | JWT creation & validation |
| **SQLAlchemy 2.0** | Async ORM for PostgreSQL |
| **asyncpg** | PostgreSQL async driver |
| **Alembic** | Database migrations |
| **Pydantic v2** | Request/response validation |
| **Redis (via redis-py)** | Token blacklist + permission cache |
| **structlog** | Structured logging (consistent with docu-store) |

### Identity SDK
| Library | Purpose |
|---------|---------|
| **PyJWT** | JWT validation (local, no service call) |
| **httpx** | Async HTTP client for identity service calls |
| **cryptography** | RSA/EC key handling for JWT verification |

---

## Project Structure

```
identity-service/
├── service/                         # The FastAPI microservice
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app + lifespan
│   │   ├── config.py                # Pydantic settings
│   │   ├── database.py              # SQLAlchemy engine + session
│   │   ├── models/                  # SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── workspace.py
│   │   │   ├── group.py
│   │   │   └── permission.py
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── workspace.py
│   │   │   ├── group.py
│   │   │   └── permission.py
│   │   ├── services/                # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py      # OAuth2 flow + JWT issuance
│   │   │   ├── user_service.py
│   │   │   ├── workspace_service.py
│   │   │   ├── group_service.py
│   │   │   └── permission_service.py
│   │   ├── auth/                    # OAuth2 provider configs
│   │   │   ├── __init__.py
│   │   │   ├── providers.py         # Google, GitHub, EntraID, generic OIDC
│   │   │   └── jwt.py               # JWT encode/decode/keys
│   │   └── api/                     # FastAPI routers
│   │       ├── __init__.py
│   │       ├── auth_routes.py
│   │       ├── user_routes.py
│   │       ├── workspace_routes.py
│   │       ├── group_routes.py
│   │       └── permission_routes.py
│   ├── migrations/                  # Alembic
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── Dockerfile
├── sdk/                             # Thin Python SDK (pip-installable)
│   ├── src/
│   │   └── identity_sdk/
│   │       ├── __init__.py
│   │       ├── middleware.py        # JWTAuthMiddleware for FastAPI
│   │       ├── dependencies.py      # get_current_user, require_role, etc.
│   │       ├── permissions.py       # PermissionClient (calls identity service)
│   │       └── types.py             # AuthenticatedUser, WorkspaceContext
│   └── pyproject.toml
├── docker-compose.yml               # PostgreSQL + Redis + service (local dev)
├── docs/
│   └── PLAN.md                      # This plan document
├── .env.example
└── README.md
```

**docu-store consumes the SDK** via:
- Dev: `pip install -e /path/to/identity-service/sdk`
- Prod: Published to PyPI or private registry

**Docker networking**: Identity service containers join `docu_store-network` (external, already exists) so docu-store can reach it.

---

## Phasing

### Phase 1: Identity Service Core (auth + workspaces)
- PostgreSQL + SQLAlchemy models (users, workspaces, memberships)
- OAuth2 login flow (Google + GitHub via Authlib)
- JWT issuance (access + refresh tokens)
- Workspace CRUD + member management
- Docker container + Alembic migrations
- **No entity permissions yet — just workspace-level roles**

### Phase 2: Groups + Entity Permissions
- Group CRUD + group membership
- Generic resource permission model
- Permission checking API (batch check)
- Permission caching (Redis)

### Phase 3: Identity SDK + docu-store Integration
- JWT validation middleware
- FastAPI dependency helpers (get_current_user, require_role)
- Permission client wrapper
- docu-store: add workspace_id/owner_id to aggregates
- docu-store: update read models, projectors, queries
- docu-store: update Qdrant stores with workspace_id filtering
- docu-store: wire auth middleware into API routes

### Phase 4: EntraID + Generic OIDC
- Microsoft EntraID provider config
- Generic OIDC provider support (Okta, Auth0, Keycloak, etc.)
- Provider management API
- Note: Authlib treats all OIDC providers uniformly, so this is mostly configuration

### Phase 5: Frontend Integration (future, separate plan)
- Replace auth stub with real OAuth2 flow
- Workspace switcher UI
- Entity sharing dialogs
- Permission-aware UI (disable buttons based on role)

---

## Docker / Infrastructure

The identity-service repo has its **own docker-compose.yml** (PostgreSQL + Redis + service). It joins the shared `docu_store-network` (external) so docu-store can reach it.

```yaml
# identity-service/docker-compose.yml
services:
  identity-postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: identity
      POSTGRES_USER: identity
      POSTGRES_PASSWORD: identity_dev
    ports:
      - "90001:5432"
    volumes:
      - identity_pg_data:/var/lib/postgresql/data
    networks:
      - docu_store-network

  identity-redis:
    image: redis:7-alpine
    ports:
      - "90002:6379"
    networks:
      - docu_store-network

  identity-service:
    build: ./service
    ports:
      - "90003:90003"
    environment:
      DATABASE_URL: postgresql+asyncpg://identity:identity_dev@identity-postgres:5432/identity
      REDIS_URL: redis://identity-redis:6379/0
      JWT_PRIVATE_KEY_PATH: /keys/private.pem
      JWT_PUBLIC_KEY_PATH: /keys/public.pem
      GOOGLE_CLIENT_ID: ${GOOGLE_CLIENT_ID}
      GOOGLE_CLIENT_SECRET: ${GOOGLE_CLIENT_SECRET}
      GITHUB_CLIENT_ID: ${GITHUB_CLIENT_ID}
      GITHUB_CLIENT_SECRET: ${GITHUB_CLIENT_SECRET}
    depends_on:
      - identity-postgres
      - identity-redis
    networks:
      - docu_store-network

volumes:
  identity_pg_data:

networks:
  docu_store-network:
    external: true
```

**Dev workflow**: Run `docker compose up` in identity-service repo + `make docker-up` in docu-store repo. Both share the network.

---

## Migration Strategy for Existing Data

Existing data has no `workspace_id` or `owner_id`. Strategy:

**Auto-migrate**: A one-time script creates a "default" workspace + "system" user, then patches all existing MongoDB documents and Qdrant points with `workspace_id=default, owner_id=system`. This is cleaner than lazy migration — no conditional logic in production code.

---

## Verification Plan

1. **Identity service**: Start with Docker, run Alembic migrations, verify OAuth2 flow with Google/GitHub, verify JWT issuance
2. **SDK**: Unit test JWT validation, mock permission checks
3. **docu-store integration**: Create artifact with workspace context, verify it appears only in that workspace's queries, verify cross-workspace isolation
4. **Qdrant**: Search should only return results from the requesting workspace
5. **Permission check**: Create private artifact, verify other workspace members can't access it, share it, verify access
