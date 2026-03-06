# Service-to-Service Authentication

Consuming applications authenticate with the Identity Service using the `X-Service-Key` header. This mechanism ensures that only authorized backend services can call permission and role endpoints, while also identifying which application is making the request.

## Service Apps

Service API keys are managed through the **service apps** system, not environment variables. Each service app is created via the admin panel (`/admin/service-apps`) or admin API and is bound to a specific `service_name`.

When a service app is created, a plaintext API key (prefixed with `sk_`) is returned **once**. The key is stored as a SHA-256 hash and cannot be retrieved again. Use the key in the `X-Service-Key` header:

```
X-Service-Key: sk_a1b2c3d4e5f6...
```

The Identity Service validates the key by hashing it and matching against active service apps via `service_app_service.validate_key()`. If the key is missing, invalid, or belongs to an inactive app, the request is rejected with `401 Unauthorized`.

### Service App Fields

| Field | Description |
|-------|-------------|
| `name` | Human-readable label for the application |
| `service_name` | The service this key is scoped to (e.g., `"docu-store"`) |
| `key_hash` | SHA-256 hash of the plaintext key |
| `key_prefix` | First few characters for identification (e.g., `sk_a1b2****`) |
| `is_active` | Can be deactivated to block requests without deleting |
| `last_used_at` | Timestamp of last successful validation |

### Managing Service Apps

```
POST   /admin/service-apps              # Create (returns plaintext key once)
GET    /admin/service-apps              # List all
GET    /admin/service-apps/{id}         # Get one
PATCH  /admin/service-apps/{id}         # Update name or is_active
DELETE /admin/service-apps/{id}         # Delete
POST   /admin/service-apps/{id}/rotate-key  # Rotate key (returns new plaintext key)
```

## X-Service-Key Header

Every request to the `/permissions/*` and `/roles/*` endpoints must include a valid service API key:

```
X-Service-Key: sk_a1b2c3d4e5f6...
```

### Service Name Scoping

Each key is bound to a `service_name`. The `verify_service_scope()` dependency ensures the key is authorized for the service being accessed. For example, a key created for `"docu-store"` cannot be used to register actions for `"analytics"`.

## Auth Tiers

Permission and role endpoints use two authentication tiers depending on the operation:

| Tier | Authentication Required | Endpoints |
|------|------------------------|-----------|
| **Dual auth** | `X-Service-Key` + user `Authorization: Bearer` JWT | `POST /permissions/check` |
| | | `POST /permissions/accessible` |
| | | `POST /permissions/{id}/share` |
| **Service-only** | `X-Service-Key` only | `POST /permissions/register` |
| | | `PATCH /permissions/{id}/visibility` |
| | | `DELETE /permissions/{id}/share` |
| | | `GET /permissions/resource/{service}/{type}/{id}` |

### Dual Auth Endpoints

These endpoints need both a service key (to authenticate the calling service) and a user JWT (to identify the user whose permissions are being checked or modified). The user context (user ID, workspace ID, workspace role, groups) is extracted from the JWT.

Example request:

```bash
curl -X POST https://identity.example.com/permissions/check \
  -H "X-Service-Key: sk_a1b2c3d4e5f6..." \
  -H "Authorization: Bearer eyJhbGciOi..." \
  -H "Content-Type: application/json" \
  -d '{
    "checks": [{
      "service_name": "docu-store",
      "resource_type": "document",
      "resource_id": "doc-uuid",
      "action": "edit"
    }]
  }'
```

### Service-Only Endpoints

These endpoints perform administrative operations on behalf of the service (registering resources, managing visibility, revoking shares). They do not require a user JWT because the action is taken by the service itself, not on behalf of a specific user.

Example request:

```bash
curl -X POST https://identity.example.com/permissions/register \
  -H "X-Service-Key: sk_a1b2c3d4e5f6..." \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "docu-store",
    "resource_type": "document",
    "resource_id": "new-doc-uuid",
    "workspace_id": "workspace-uuid",
    "owner_id": "creator-user-uuid",
    "visibility": "workspace"
  }'
```

## Dev Setup

Service keys are always enforced — even in development. Before calling any service-key-protected endpoint, create a service app via the admin panel:

1. Start the service (`make start`) and admin panel (`make admin`)
2. Sign in at [http://localhost:9004](http://localhost:9004)
3. Navigate to **Service Apps** → **Add Service App**
4. Copy the generated `sk_...` key into your consuming service's `.env`

If no active service apps exist, the service logs a warning at startup and all service-key endpoints return 401.

## Production Configuration

### Creating a Service App

1. Log in to the admin panel at `{ADMIN_URL}`
2. Navigate to **Service Apps**
3. Click **Create Service App** and provide a name and service name
4. Copy the plaintext key from the response -- it is shown only once

Or via the admin API:

```bash
curl -X POST https://identity.example.com/admin/service-apps \
  -H "Cookie: admin_token=..." \
  -H "Content-Type: application/json" \
  -d '{"name": "Docu-Store Production", "service_name": "docu-store"}'
```

The response includes the plaintext key:

```json
{
  "id": "...",
  "name": "Docu-Store Production",
  "service_name": "docu-store",
  "key_prefix": "sk_a1b2****",
  "key": "sk_a1b2c3d4e5f6g7h8..."
}
```

### Key Rotation

Rotate a key without downtime:

1. Call `POST /admin/service-apps/{id}/rotate-key` to generate a new key (the old key is immediately invalidated)
2. Update all consuming services to use the new key

For zero-downtime rotation, create a second service app with the same `service_name`, update consuming services, then deactivate the old app.

## SDK Integration

The Python SDK's `PermissionClient` and `RoleClient` handle service key headers automatically:

```python
from sentinel_auth.permissions import PermissionClient

client = PermissionClient(
    base_url="https://identity.example.com",
    service_name="docu-store",
    service_key="sk_a1b2c3d4e5f6...",
)

# Dual auth: pass the user's JWT token
result = await client.can(
    token="user-jwt-here",
    resource_type="document",
    resource_id="doc-uuid",
    action="edit",
)

# Service-only: no token needed
await client.register_resource(
    resource_type="document",
    resource_id="new-doc-uuid",
    workspace_id="workspace-uuid",
    owner_id="creator-uuid",
)
```

The SDK's `_headers(token=None)` method builds the appropriate headers:

- Always includes `X-Service-Key` if a `service_key` was provided.
- Includes `Authorization: Bearer {token}` when a user token is passed.
