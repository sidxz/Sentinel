# Users, Workspaces & Groups

All endpoints in this section require a Bearer JWT in the `Authorization` header.

---

## Users

### GET /users/me

Returns the authenticated user's profile.

**Response:** `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "jane@example.com",
  "name": "Jane Doe",
  "avatar_url": "https://example.com/avatar.jpg",
  "is_active": true,
  "created_at": "2025-07-01T14:00:00Z"
}
```

```bash
curl http://localhost:9003/users/me \
  -H "Authorization: Bearer eyJhbGciOi..."
```

### PATCH /users/me

Updates the authenticated user's profile. Both fields are optional.

**Request Body:**

```json
{"name": "Jane Smith", "avatar_url": "https://example.com/new-avatar.jpg"}
```

**Response:** `200 OK` -- updated `UserResponse`.

---

## Workspaces

### Endpoint Table

| Method | Path | Min Role | Description |
|---|---|---|---|
| POST | `/workspaces` | any | Create workspace (caller becomes owner) |
| GET | `/workspaces` | any | List user's workspaces |
| GET | `/workspaces/{id}` | any | Get workspace details |
| PATCH | `/workspaces/{id}` | admin | Update workspace |
| DELETE | `/workspaces/{id}` | owner | Delete workspace |
| GET | `/workspaces/{id}/members` | any | List members |
| POST | `/workspaces/{id}/members/invite` | admin | Invite member |
| PATCH | `/workspaces/{id}/members/{user_id}` | admin | Change member role |
| DELETE | `/workspaces/{id}/members/{user_id}` | admin | Remove member |

The JWT's `wid` claim must match the `{id}` path parameter. Cross-workspace access returns `403`.

### POST /workspaces

**Request Body:**

```json
{"name": "Acme Corp", "slug": "acme-corp", "description": "Main workspace"}
```

Slug must match `^[a-z0-9][a-z0-9-]*[a-z0-9]$`.

**Response:** `201 Created` -- `WorkspaceResponse`.

### GET /workspaces

Returns all workspaces the authenticated user belongs to.

**Response:** `200 OK` -- `WorkspaceResponse[]`.

### PATCH /workspaces/{id}

**Request Body:**

```json
{"name": "New Name", "description": "Updated description"}
```

**Response:** `200 OK` -- updated `WorkspaceResponse`.

### DELETE /workspaces/{id}

**Response:** `204 No Content`.

### POST /workspaces/{id}/members/invite

**Request Body:**

```json
{"email": "bob@example.com", "role": "editor"}
```

Role must be one of: `owner`, `admin`, `editor`, `viewer` (default: `viewer`).

**Response:** `201 Created` -- `WorkspaceMemberResponse`.

### PATCH /workspaces/{id}/members/{user_id}

**Request Body:**

```json
{"role": "admin"}
```

**Response:** `200 OK` -- updated membership.

### DELETE /workspaces/{id}/members/{user_id}

**Response:** `204 No Content`.

---

## Groups

Groups are scoped to a workspace. All routes are under `/workspaces/{workspace_id}/groups`.

### Endpoint Table

| Method | Path | Min Role | Description |
|---|---|---|---|
| POST | `/workspaces/{wid}/groups` | admin | Create group |
| GET | `/workspaces/{wid}/groups` | any | List groups |
| PATCH | `/workspaces/{wid}/groups/{gid}` | admin | Update group |
| DELETE | `/workspaces/{wid}/groups/{gid}` | admin | Delete group |
| POST | `/workspaces/{wid}/groups/{gid}/members/{uid}` | admin | Add member |
| DELETE | `/workspaces/{wid}/groups/{gid}/members/{uid}` | admin | Remove member |

### POST /workspaces/{workspace_id}/groups

**Request Body:**

```json
{"name": "Engineering", "description": "Engineering team"}
```

**Response:** `201 Created` -- `GroupResponse`.

### PATCH /workspaces/{workspace_id}/groups/{group_id}

**Request Body:**

```json
{"name": "Platform Engineering"}
```

**Response:** `200 OK` -- updated `GroupResponse`.

### POST /workspaces/{workspace_id}/groups/{group_id}/members/{user_id}

**Response:** `201 Created`

```json
{"status": "ok"}
```

### DELETE /workspaces/{workspace_id}/groups/{group_id}/members/{user_id}

**Response:** `204 No Content`.
