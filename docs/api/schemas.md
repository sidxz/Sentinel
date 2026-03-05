# Schema Reference

> **Tip:** For interactive API exploration, visit `/docs` (Swagger UI) when the service is running.

This page consolidates all Pydantic request and response models used by the Daikon Identity Service API. Each schema is presented as a table with field details.

---

## Auth Schemas

### TokenResponse

Returned by `POST /auth/refresh` after a successful token rotation.

| Field | Type | Required | Description |
|---|---|---|---|
| `access_token` | `string` | Yes | RS256-signed JWT access token |
| `refresh_token` | `string` | Yes | Opaque refresh token for obtaining new access tokens |
| `token_type` | `string` | Yes | Always `"bearer"` |
| `expires_in` | `integer` | Yes | Access token TTL in seconds |

### RefreshRequest

Request body for `POST /auth/refresh`.

| Field | Type | Required | Description |
|---|---|---|---|
| `refresh_token` | `string` | Yes | The refresh token to exchange |

### TokenPayload

Internal JWT payload structure. Not directly returned by any endpoint, but useful for understanding JWT claims.

| Field | Type | Required | Description |
|---|---|---|---|
| `sub` | `UUID` | Yes | User ID |
| `email` | `string` | Yes | User email address |
| `name` | `string` | Yes | User display name |
| `wid` | `UUID` | Yes | Active workspace ID |
| `wslug` | `string` | Yes | Active workspace slug |
| `wrole` | `string` | Yes | User's role in the active workspace (`viewer`, `editor`, `admin`, `owner`) |
| `groups` | `list[UUID]` | Yes | List of group IDs the user belongs to in the active workspace |

### ProviderListResponse

Returned by `GET /auth/providers`.

| Field | Type | Required | Description |
|---|---|---|---|
| `providers` | `list[string]` | Yes | List of configured OAuth provider names (e.g., `["google", "github"]`) |

---

## User Schemas

### UserResponse

Returned by `GET /users/me` and `PATCH /users/me`.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `UUID` | Yes | User ID |
| `email` | `string` | Yes | User email address |
| `name` | `string` | Yes | User display name |
| `avatar_url` | `string \| null` | Yes | URL to user's avatar image, or `null` |
| `is_active` | `boolean` | Yes | Whether the user account is active |
| `created_at` | `datetime` | Yes | Account creation timestamp (ISO 8601) |

### UserUpdateRequest

Request body for `PATCH /users/me`.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string \| null` | No | New display name |
| `avatar_url` | `string \| null` | No | New avatar URL |

---

## Workspace Schemas

### WorkspaceCreateRequest

Request body for `POST /workspaces`.

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `name` | `string` | Yes | 1-255 characters | Workspace display name |
| `slug` | `string` | Yes | 1-100 chars, pattern: `^[a-z0-9][a-z0-9-]*[a-z0-9]$` | URL-safe workspace identifier. Must start and end with a lowercase alphanumeric character; hyphens allowed in between. |
| `description` | `string \| null` | No | -- | Optional workspace description |

### WorkspaceUpdateRequest

Request body for `PATCH /workspaces/{id}`.

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `name` | `string \| null` | No | 1-255 characters | New workspace name |
| `description` | `string \| null` | No | -- | New workspace description |

### WorkspaceResponse

Returned by workspace CRUD endpoints.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `UUID` | Yes | Workspace ID |
| `slug` | `string` | Yes | URL-safe workspace identifier |
| `name` | `string` | Yes | Workspace display name |
| `description` | `string \| null` | Yes | Workspace description, or `null` |
| `created_by` | `UUID` | Yes | ID of the user who created the workspace |
| `created_at` | `datetime` | Yes | Creation timestamp (ISO 8601) |

### WorkspaceMemberResponse

Returned by member listing and invite endpoints.

| Field | Type | Required | Description |
|---|---|---|---|
| `user_id` | `UUID` | Yes | Member's user ID |
| `email` | `string` | Yes | Member's email address |
| `name` | `string` | Yes | Member's display name |
| `avatar_url` | `string \| null` | Yes | Member's avatar URL, or `null` |
| `role` | `string` | Yes | Workspace role: `viewer`, `editor`, `admin`, or `owner` |
| `joined_at` | `datetime` | Yes | When the member joined the workspace (ISO 8601) |

### InviteMemberRequest

Request body for `POST /workspaces/{id}/members/invite`.

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `email` | `string` | Yes | -- | Email address of the user to invite |
| `role` | `string` | No | Pattern: `^(owner\|admin\|editor\|viewer)$`. Default: `viewer` | Role to assign to the invited member |

### UpdateMemberRoleRequest

Request body for `PATCH /workspaces/{id}/members/{user_id}`.

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `role` | `string` | Yes | Pattern: `^(owner\|admin\|editor\|viewer)$` | New role for the member |

---

## Group Schemas

### GroupCreateRequest

Request body for `POST /workspaces/{workspace_id}/groups`.

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `name` | `string` | Yes | 1-255 characters | Group display name |
| `description` | `string \| null` | No | -- | Optional group description |

### GroupUpdateRequest

Request body for `PATCH /workspaces/{workspace_id}/groups/{group_id}`.

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `name` | `string \| null` | No | 1-255 characters | New group name |
| `description` | `string \| null` | No | -- | New group description |

### GroupResponse

Returned by group CRUD endpoints.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `UUID` | Yes | Group ID |
| `workspace_id` | `UUID` | Yes | Parent workspace ID |
| `name` | `string` | Yes | Group display name |
| `description` | `string \| null` | Yes | Group description, or `null` |
| `created_by` | `UUID` | Yes | ID of the user who created the group |
| `created_at` | `datetime` | Yes | Creation timestamp (ISO 8601) |

### GroupMemberResponse

Returned when listing group members.

| Field | Type | Required | Description |
|---|---|---|---|
| `user_id` | `UUID` | Yes | Member's user ID |
| `email` | `string` | Yes | Member's email address |
| `name` | `string` | Yes | Member's display name |
| `added_at` | `datetime` | Yes | When the member was added to the group (ISO 8601) |

---

## Permission Schemas

### PermissionCheckItem

Individual permission check within a [PermissionCheckRequest](#permissioncheckrequest). Not used directly as a request body.

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `service_name` | `string` | Yes | -- | Name of the service that owns the resource |
| `resource_type` | `string` | Yes | -- | Type of resource (e.g., `document`, `project`) |
| `resource_id` | `UUID` | Yes | -- | Resource ID |
| `action` | `string` | Yes | Pattern: `^(view\|edit)$` | Action to check |

### PermissionCheckRequest

Request body for `POST /permissions/check`.

| Field | Type | Required | Description |
|---|---|---|---|
| `checks` | `list[PermissionCheckItem]` | Yes | List of permission checks to evaluate |

### PermissionCheckResult

Individual result within a [PermissionCheckResponse](#permissioncheckresponse).

| Field | Type | Required | Description |
|---|---|---|---|
| `service_name` | `string` | Yes | Service name from the check |
| `resource_type` | `string` | Yes | Resource type from the check |
| `resource_id` | `UUID` | Yes | Resource ID from the check |
| `action` | `string` | Yes | Action that was checked |
| `allowed` | `boolean` | Yes | Whether the action is permitted |

### PermissionCheckResponse

Returned by `POST /permissions/check`.

| Field | Type | Required | Description |
|---|---|---|---|
| `results` | `list[PermissionCheckResult]` | Yes | Results for each requested permission check |

### RegisterResourceRequest

Request body for `POST /permissions/register`.

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `service_name` | `string` | Yes | -- | Name of the service registering the resource |
| `resource_type` | `string` | Yes | -- | Type of resource |
| `resource_id` | `UUID` | Yes | -- | Unique resource identifier |
| `workspace_id` | `UUID` | Yes | -- | Workspace the resource belongs to |
| `owner_id` | `UUID` | Yes | -- | User ID of the resource owner |
| `visibility` | `string` | No | Pattern: `^(private\|workspace)$`. Default: `workspace` | Resource visibility level |

### ShareRequest

Request body for `POST /permissions/{id}/share` and `DELETE /permissions/{id}/share`.

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `grantee_type` | `string` | Yes | Pattern: `^(user\|group)$` | Whether sharing with a user or a group |
| `grantee_id` | `UUID` | Yes | -- | ID of the user or group to share with |
| `permission` | `string` | Yes | Pattern: `^(view\|edit)$` | Permission level to grant |

### UpdateVisibilityRequest

Request body for `PATCH /permissions/{id}/visibility`.

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `visibility` | `string` | Yes | Pattern: `^(private\|workspace)$` | New visibility level |

### ResourcePermissionResponse

Returned by resource registration, visibility update, and ACL retrieval endpoints.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `UUID` | Yes | Permission record ID |
| `service_name` | `string` | Yes | Service that owns the resource |
| `resource_type` | `string` | Yes | Type of the resource |
| `resource_id` | `UUID` | Yes | Resource ID |
| `workspace_id` | `UUID` | Yes | Workspace the resource belongs to |
| `owner_id` | `UUID` | Yes | User ID of the resource owner |
| `visibility` | `string` | Yes | Current visibility: `private` or `workspace` |
| `created_at` | `datetime` | Yes | When the resource was registered (ISO 8601) |
| `shares` | `list[ResourceShareResponse]` | Yes | List of active shares for this resource |

### ResourceShareResponse

Nested within [ResourcePermissionResponse](#resourcepermissionresponse).

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `UUID` | Yes | Share record ID |
| `grantee_type` | `string` | Yes | `user` or `group` |
| `grantee_id` | `UUID` | Yes | ID of the user or group |
| `permission` | `string` | Yes | `view` or `edit` |
| `granted_by` | `UUID` | Yes | User ID of who created the share |
| `granted_at` | `datetime` | Yes | When the share was created (ISO 8601) |

### AccessibleResourcesRequest

Request body for `POST /permissions/accessible`.

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `service_name` | `string` | Yes | -- | Service name to query |
| `resource_type` | `string` | Yes | -- | Resource type to query |
| `action` | `string` | Yes | Pattern: `^(view\|edit)$` | Action to check accessibility for |
| `workspace_id` | `UUID` | Yes | -- | Workspace to scope the query to (must match JWT) |
| `limit` | `integer \| null` | No | Min: 1, Max: 10000. Default: `null` (no limit) | Maximum number of resource IDs to return |

### AccessibleResourcesResponse

Returned by `POST /permissions/accessible`.

| Field | Type | Required | Description |
|---|---|---|---|
| `resource_ids` | `list[UUID]` | Yes | List of resource IDs the user can access |
| `has_full_access` | `boolean` | Yes | `true` if the user's workspace role grants blanket access (no need to filter by individual shares) |

---

## Role Schemas (RBAC)

### ActionDefinition

Individual action within a [RegisterActionsRequest](#registeractionsrequest).

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `action` | `string` | Yes | Pattern: `^[a-z][a-z0-9_.:-]*$` | Action identifier (e.g., `reports:export`) |
| `description` | `string \| null` | No | -- | Human-readable description of the action |

### RegisterActionsRequest

Request body for `POST /roles/actions/register`.

| Field | Type | Required | Description |
|---|---|---|---|
| `service_name` | `string` | Yes | Name of the service registering actions |
| `actions` | `list[ActionDefinition]` | Yes | List of actions to register |

### CheckActionRequest

Request body for `POST /roles/check-action`.

| Field | Type | Required | Description |
|---|---|---|---|
| `service_name` | `string` | Yes | Service to check the action for |
| `action` | `string` | Yes | Action identifier to check |
| `workspace_id` | `UUID` | Yes | Workspace to check within (must match JWT) |

### ServiceActionResponse

Returned by action registration and listing endpoints.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `UUID` | Yes | Service action record ID |
| `service_name` | `string` | Yes | Service that owns this action |
| `action` | `string` | Yes | Action identifier |
| `description` | `string \| null` | Yes | Human-readable description |
| `created_at` | `datetime` | Yes | When the action was registered (ISO 8601) |

### RoleResponse

Returned by role CRUD endpoints.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `UUID` | Yes | Role ID |
| `workspace_id` | `UUID` | Yes | Parent workspace ID |
| `name` | `string` | Yes | Role display name |
| `description` | `string \| null` | Yes | Role description |
| `created_by` | `UUID \| null` | Yes | ID of the user who created the role |
| `created_at` | `datetime` | Yes | Creation timestamp (ISO 8601) |
| `action_count` | `integer` | Yes | Number of actions assigned to this role |
| `member_count` | `integer` | Yes | Number of users assigned to this role |

### RoleCreateRequest

Request body for `POST /admin/workspaces/{id}/roles`.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | Yes | Role display name |
| `description` | `string \| null` | No | Optional role description |

### RoleUpdateRequest

Request body for `PATCH /admin/roles/{id}`.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string \| null` | No | New role name |
| `description` | `string \| null` | No | New role description |

### AddRoleActionsRequest

Request body for `POST /admin/roles/{id}/actions`.

| Field | Type | Required | Description |
|---|---|---|---|
| `service_action_ids` | `list[UUID]` | Yes | List of service action IDs to add to the role |

### RoleMemberResponse

Returned when listing role members.

| Field | Type | Required | Description |
|---|---|---|---|
| `user_id` | `UUID` | Yes | Member's user ID |
| `email` | `string` | Yes | Member's email address |
| `name` | `string` | Yes | Member's display name |
| `assigned_at` | `datetime` | Yes | When the member was assigned to the role (ISO 8601) |
| `assigned_by` | `UUID \| null` | Yes | User ID of who assigned the member |

### CheckActionResponse

Returned by `POST /roles/check-action`.

| Field | Type | Required | Description |
|---|---|---|---|
| `allowed` | `boolean` | Yes | Whether the action is permitted |
| `roles` | `list[string]` | Yes | Names of roles that grant this action |

### UserActionsResponse

Returned by `GET /roles/user-actions`.

| Field | Type | Required | Description |
|---|---|---|---|
| `actions` | `list[string]` | Yes | List of action identifiers the user can perform |
