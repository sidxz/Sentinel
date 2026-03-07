# Group Endpoints

> **Tip:** For interactive API exploration, visit `/docs` (Swagger UI) when the service is running.

The group endpoints manage groups within a workspace. Groups are used for organizing users and assigning shared permissions. All routes are nested under `/workspaces/{workspace_id}/groups` and require a valid JWT Bearer token.

## Endpoints Overview

| Method | Path | Min Role | Description |
|---|---|---|---|
| `POST` | `/workspaces/{workspace_id}/groups` | admin+ | Create a group |
| `GET` | `/workspaces/{workspace_id}/groups` | member | List groups in workspace |
| `PATCH` | `/workspaces/{workspace_id}/groups/{group_id}` | admin+ | Update a group |
| `DELETE` | `/workspaces/{workspace_id}/groups/{group_id}` | admin+ | Delete a group |
| `POST` | `/workspaces/{workspace_id}/groups/{group_id}/members/{member_user_id}` | admin+ | Add user to group |
| `DELETE` | `/workspaces/{workspace_id}/groups/{group_id}/members/{member_user_id}` | admin+ | Remove user from group |

All endpoints validate that the JWT's `workspace_id` matches the `{workspace_id}` path parameter.

---

## Group CRUD

### Create Group

Creates a new group within the workspace.

```
POST /workspaces/{workspace_id}/groups
```

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `workspace_id` | path | UUID | Yes | Workspace ID |

**Auth:** JWT Bearer token required. Minimum role: `admin`.

**Request Body:** [GroupCreateRequest](schemas.md#groupcreaterequest)

```json
{
  "name": "Engineering",
  "description": "Core engineering team"
}
```

**Response** `201 Created` -- [GroupResponse](schemas.md#groupresponse)

```json
{
  "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "workspace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "Engineering",
  "description": "Core engineering team",
  "created_by": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2025-07-01T14:00:00Z"
}
```

**curl example:**

```bash
curl -X POST http://localhost:9003/workspaces/a1b2c3d4-e5f6-7890-abcd-ef1234567890/groups \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"name": "Engineering", "description": "Core engineering team"}'
```

---

### List Groups

Returns all groups in the workspace.

```
GET /workspaces/{workspace_id}/groups
```

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `workspace_id` | path | UUID | Yes | Workspace ID |

**Auth:** JWT Bearer token required. Must be a member.

**Response** `200 OK` -- `list[GroupResponse]`

```json
[
  {
    "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "workspace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "name": "Engineering",
    "description": "Core engineering team",
    "created_by": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2025-07-01T14:00:00Z"
  }
]
```

**curl example:**

```bash
curl http://localhost:9003/workspaces/a1b2c3d4-e5f6-7890-abcd-ef1234567890/groups \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..."
```

---

### Update Group

Updates a group's name and/or description.

```
PATCH /workspaces/{workspace_id}/groups/{group_id}
```

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `workspace_id` | path | UUID | Yes | Workspace ID |
| `group_id` | path | UUID | Yes | Group ID |

**Auth:** JWT Bearer token required. Minimum role: `admin`.

**Request Body:** [GroupUpdateRequest](schemas.md#groupupdaterequest)

```json
{
  "name": "Platform Engineering",
  "description": "Renamed team"
}
```

**Response** `200 OK` -- [GroupResponse](schemas.md#groupresponse)

**curl example:**

```bash
curl -X PATCH http://localhost:9003/workspaces/a1b2c3d4-e5f6-7890-abcd-ef1234567890/groups/b2c3d4e5-f6a7-8901-bcde-f12345678901 \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"name": "Platform Engineering"}'
```

---

### Delete Group

Permanently deletes a group and all its membership records.

```
DELETE /workspaces/{workspace_id}/groups/{group_id}
```

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `workspace_id` | path | UUID | Yes | Workspace ID |
| `group_id` | path | UUID | Yes | Group ID |

**Auth:** JWT Bearer token required. Minimum role: `admin`.

**Response** `204 No Content`

---

## Group Membership

### Add Member to Group

Adds a user to a group.

```
POST /workspaces/{workspace_id}/groups/{group_id}/members/{member_user_id}
```

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `workspace_id` | path | UUID | Yes | Workspace ID |
| `group_id` | path | UUID | Yes | Group ID |
| `member_user_id` | path | UUID | Yes | User ID to add |

**Auth:** JWT Bearer token required. Minimum role: `admin`.

**Response** `201 Created`

```json
{
  "status": "ok"
}
```

**curl example:**

```bash
curl -X POST http://localhost:9003/workspaces/a1b2c3d4-e5f6-7890-abcd-ef1234567890/groups/b2c3d4e5-f6a7-8901-bcde-f12345678901/members/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..."
```

---

### Remove Member from Group

Removes a user from a group.

```
DELETE /workspaces/{workspace_id}/groups/{group_id}/members/{member_user_id}
```

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `workspace_id` | path | UUID | Yes | Workspace ID |
| `group_id` | path | UUID | Yes | Group ID |
| `member_user_id` | path | UUID | Yes | User ID to remove |

**Auth:** JWT Bearer token required. Minimum role: `admin`.

**Response** `204 No Content`

**curl example:**

```bash
curl -X DELETE http://localhost:9003/workspaces/a1b2c3d4-e5f6-7890-abcd-ef1234567890/groups/b2c3d4e5-f6a7-8901-bcde-f12345678901/members/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..."
```
