# Workspace Endpoints

> **Tip:** For interactive API exploration, visit `/docs` (Swagger UI) when the service is running.

The workspace endpoints manage workspaces and their members. All routes are under the `/workspaces` prefix and require a valid JWT Bearer token. Some operations require a minimum workspace role as indicated below.

## Role Hierarchy

Workspace roles follow this hierarchy (lowest to highest):

```
viewer < editor < admin < owner
```

Endpoints annotated with a minimum role (e.g., "admin+") require that role or higher.

## Endpoints Overview

| Method | Path | Min Role | Description |
|---|---|---|---|
| `POST` | `/workspaces` | any authenticated | Create a new workspace |
| `GET` | `/workspaces` | any authenticated | List user's workspaces |
| `GET` | `/workspaces/{id}` | member | Get workspace details |
| `PATCH` | `/workspaces/{id}` | admin+ | Update workspace |
| `DELETE` | `/workspaces/{id}` | owner | Delete workspace |
| `GET` | `/workspaces/{id}/members` | member | List workspace members |
| `POST` | `/workspaces/{id}/members/invite` | admin+ | Invite a member |
| `PATCH` | `/workspaces/{id}/members/{user_id}` | admin+ | Update member role |
| `DELETE` | `/workspaces/{id}/members/{user_id}` | admin+ | Remove a member |

---

## Workspace CRUD

### Create Workspace

Creates a new workspace. The authenticated user becomes the owner.

```
POST /workspaces
```

**Auth:** JWT Bearer token required.

**Request Body:** [WorkspaceCreateRequest](schemas.md#workspacecreaterequest)

```json
{
  "name": "Acme Corp",
  "slug": "acme-corp",
  "description": "Main workspace for Acme Corp"
}
```

**Response** `201 Created` -- [WorkspaceResponse](schemas.md#workspaceresponse)

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "slug": "acme-corp",
  "name": "Acme Corp",
  "description": "Main workspace for Acme Corp",
  "created_by": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2025-06-15T10:30:00Z"
}
```

**curl example:**

```bash
curl -X POST http://localhost:9003/workspaces \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "slug": "acme-corp",
    "description": "Main workspace for Acme Corp"
  }'
```

---

### List Workspaces

Returns all workspaces the authenticated user is a member of.

```
GET /workspaces
```

**Auth:** JWT Bearer token required.

**Response** `200 OK` -- `list[WorkspaceResponse]`

```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "slug": "acme-corp",
    "name": "Acme Corp",
    "description": "Main workspace for Acme Corp",
    "created_by": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2025-06-15T10:30:00Z"
  }
]
```

---

### Get Workspace

Returns details for a specific workspace. The JWT must contain a matching `workspace_id`.

```
GET /workspaces/{workspace_id}
```

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `workspace_id` | path | UUID | Yes | Workspace ID |

**Auth:** JWT Bearer token required. Must be a member of the workspace.

**Response** `200 OK` -- [WorkspaceResponse](schemas.md#workspaceresponse)

**Errors:**

| Code | Detail |
|---|---|
| `403` | Not a member of this workspace |
| `404` | Workspace not found |

---

### Update Workspace

Updates workspace name and/or description. Requires `admin` role or higher.

```
PATCH /workspaces/{workspace_id}
```

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `workspace_id` | path | UUID | Yes | Workspace ID |

**Auth:** JWT Bearer token required. Minimum role: `admin`.

**Request Body:** [WorkspaceUpdateRequest](schemas.md#workspaceupdaterequest)

```json
{
  "name": "Acme Corporation",
  "description": "Updated description"
}
```

**Response** `200 OK` -- [WorkspaceResponse](schemas.md#workspaceresponse)

**Errors:**

| Code | Detail |
|---|---|
| `403` | Not a member of this workspace / Insufficient role |

---

### Delete Workspace

Permanently deletes a workspace. Requires `owner` role.

```
DELETE /workspaces/{workspace_id}
```

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `workspace_id` | path | UUID | Yes | Workspace ID |

**Auth:** JWT Bearer token required. Minimum role: `owner`.

**Response** `204 No Content`

**Errors:**

| Code | Detail |
|---|---|
| `403` | Not a member of this workspace / Insufficient role |

---

## Member Management

### List Members

Returns all members of a workspace with their roles.

```
GET /workspaces/{workspace_id}/members
```

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `workspace_id` | path | UUID | Yes | Workspace ID |

**Auth:** JWT Bearer token required. Must be a member.

**Response** `200 OK` -- `list[WorkspaceMemberResponse]`

```json
[
  {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "jane@example.com",
    "name": "Jane Doe",
    "avatar_url": "https://avatars.example.com/jane.png",
    "role": "owner",
    "joined_at": "2025-06-15T10:30:00Z"
  },
  {
    "user_id": "660e8400-e29b-41d4-a716-446655440001",
    "email": "bob@example.com",
    "name": "Bob Smith",
    "avatar_url": null,
    "role": "editor",
    "joined_at": "2025-07-01T14:00:00Z"
  }
]
```

---

### Invite Member

Invites a user to the workspace by email. If the user exists, they are added as a member with the specified role.

```
POST /workspaces/{workspace_id}/members/invite
```

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `workspace_id` | path | UUID | Yes | Workspace ID |

**Auth:** JWT Bearer token required. Minimum role: `admin`.

**Request Body:** [InviteMemberRequest](schemas.md#invitememberrequest)

```json
{
  "email": "bob@example.com",
  "role": "editor"
}
```

**Response** `201 Created` -- [WorkspaceMemberResponse](schemas.md#workspacememberresponse)

```json
{
  "user_id": "660e8400-e29b-41d4-a716-446655440001",
  "email": "bob@example.com",
  "name": "Bob Smith",
  "avatar_url": null,
  "role": "editor",
  "joined_at": "2025-07-01T14:00:00Z"
}
```

**curl example:**

```bash
curl -X POST http://localhost:9003/workspaces/a1b2c3d4-e5f6-7890-abcd-ef1234567890/members/invite \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"email": "bob@example.com", "role": "editor"}'
```

---

### Update Member Role

Changes the role of an existing workspace member.

```
PATCH /workspaces/{workspace_id}/members/{user_id}
```

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `workspace_id` | path | UUID | Yes | Workspace ID |
| `user_id` | path | UUID | Yes | Target user ID |

**Auth:** JWT Bearer token required. Minimum role: `admin`.

**Request Body:** [UpdateMemberRoleRequest](schemas.md#updatememberrolerequest)

```json
{
  "role": "admin"
}
```

**Response** `200 OK` -- Returns a [WorkspaceMemberResponse](schemas.md#workspacememberresponse).

**Errors:**

| Code | Detail |
|---|---|
| `403` | Not a member of this workspace / Insufficient role |

---

### Remove Member

Removes a user from the workspace.

```
DELETE /workspaces/{workspace_id}/members/{user_id}
```

| Parameter | In | Type | Required | Description |
|---|---|---|---|---|
| `workspace_id` | path | UUID | Yes | Workspace ID |
| `user_id` | path | UUID | Yes | Target user ID |

**Auth:** JWT Bearer token required. Minimum role: `admin`.

**Response** `204 No Content`

**Errors:**

| Code | Detail |
|---|---|
| `403` | Not a member of this workspace / Insufficient role |
