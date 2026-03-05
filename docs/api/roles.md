# Role Endpoints

> **Tip:** For interactive API exploration, visit `/docs` (Swagger UI) when the service is running.

The role endpoints implement NIST Core RBAC (Level 1) -- service-scoped actions organized into workspace roles. They allow backend services to register actions, check user permissions, and query available actions. All routes are under the `/roles` prefix.

Role endpoints use two authentication tiers:

- **Service-only auth** (Service Key): For registering actions.
- **Dual auth** (Service Key + JWT): For checking and querying user actions.

## Endpoints Overview

| Method | Path | Auth Tier | Description |
|---|---|---|---|
| `POST` | `/roles/actions/register` | Service-only | Register service actions |
| `POST` | `/roles/check-action` | Dual | Check if user can perform an action |
| `GET` | `/roles/user-actions` | Dual | List all actions user can perform |

---

## Service-Only Endpoints

### Register Actions

Registers actions for a service. Idempotent -- existing actions get their descriptions updated, new actions are created.

```
POST /roles/actions/register
```

**Request Body:** [RegisterActionsRequest](schemas.md#registeractionsrequest)

```json
{
  "service_name": "analytics",
  "actions": [
    {"action": "reports:export", "description": "Export reports as CSV/PDF"},
    {"action": "reports:view", "description": "View report data"},
    {"action": "dashboards:create", "description": "Create new dashboards"}
  ]
}
```

**Response** `201 Created` -- list of [ServiceActionResponse](schemas.md#serviceactionresponse)

```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "service_name": "analytics",
    "action": "reports:export",
    "description": "Export reports as CSV/PDF",
    "created_at": "2025-07-01T14:00:00Z"
  }
]
```

**curl example:**

```bash
curl -X POST http://localhost:9003/roles/actions/register \
  -H "X-Service-Key: sk_your_service_key" \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "analytics",
    "actions": [
      {"action": "reports:export", "description": "Export reports"}
    ]
  }'
```

---

## Dual Auth Endpoints

These endpoints require both the `X-Service-Key` header and a JWT `Authorization` header.

### Check Action

Checks whether the current user can perform a specific action in a workspace. Returns the list of roles that grant the action.

```
POST /roles/check-action
```

**Request Body:** [CheckActionRequest](schemas.md#checkactionrequest)

```json
{
  "service_name": "analytics",
  "action": "reports:export",
  "workspace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Response** `200 OK` -- [CheckActionResponse](schemas.md#checkactionresponse)

```json
{
  "allowed": true,
  "roles": ["Analyst", "Power User"]
}
```

**Errors:**

| Code | Detail |
|---|---|
| `403` | Cross-workspace check not allowed (JWT workspace must match request workspace) |

**curl example:**

```bash
curl -X POST http://localhost:9003/roles/check-action \
  -H "X-Service-Key: sk_your_service_key" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "analytics",
    "action": "reports:export",
    "workspace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }'
```

---

### List User Actions

Returns all actions the current user can perform for a given service in a workspace.

```
GET /roles/user-actions?service_name={service_name}&workspace_id={workspace_id}
```

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `service_name` | query | string | Yes | Service to query actions for |
| `workspace_id` | query | UUID | Yes | Workspace scope |

**Response** `200 OK` -- [UserActionsResponse](schemas.md#useractionsresponse)

```json
{
  "actions": ["reports:export", "reports:view", "dashboards:create"]
}
```

**Errors:**

| Code | Detail |
|---|---|
| `403` | Cross-workspace lookup not allowed |

**curl example:**

```bash
curl "http://localhost:9003/roles/user-actions?service_name=analytics&workspace_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  -H "X-Service-Key: sk_your_service_key" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..."
```

---

## Admin Endpoints

Role management is available through the admin API. See the [Admin Panel guide](../guide/admin.md) for details.

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/service-actions` | List all registered actions |
| `GET` | `/admin/workspaces/{wid}/roles` | List workspace roles |
| `POST` | `/admin/workspaces/{wid}/roles` | Create role |
| `PATCH` | `/admin/roles/{rid}` | Update role |
| `DELETE` | `/admin/roles/{rid}` | Delete role |
| `GET` | `/admin/roles/{rid}/actions` | List role's actions |
| `POST` | `/admin/roles/{rid}/actions` | Add actions to role |
| `DELETE` | `/admin/roles/{rid}/actions/{said}` | Remove action from role |
| `GET` | `/admin/roles/{rid}/members` | List role members |
| `POST` | `/admin/roles/{rid}/members/{uid}` | Assign user to role |
| `DELETE` | `/admin/roles/{rid}/members/{uid}` | Remove user from role |
