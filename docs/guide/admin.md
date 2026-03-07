# Admin Panel

The Sentinel Auth includes an administrative panel for platform operators to manage users, workspaces, groups, permissions, and monitor system activity. The admin panel runs as a separate React application and communicates with the Sentinel API through dedicated admin endpoints.

## Overview

| Property | Value |
|----------|-------|
| Application | React SPA |
| Default port | 9004 |
| API prefix | `/admin/*` and `/auth/admin/*` |
| Authentication | HttpOnly cookie with admin JWT |

## Features

### Dashboard

The admin dashboard provides an at-a-glance view of the platform:

- **Total users**: Count of all registered users
- **Total workspaces**: Count of all workspaces
- **Recent activity**: Latest login, creation, and modification events
- **Quick stats**: Active users, workspace distribution, group counts

### User Management

Full CRUD operations on user records:

- **List users**: Paginated with search by name or email
- **View user detail**: Profile, linked social accounts, workspace memberships, group memberships
- **Update user**: Edit name, activate/deactivate accounts
- **Add to workspace**: Assign a user to a workspace with a specific role
- **CSV import**: Bulk import users from a CSV file

### Workspace Management

Full CRUD operations on workspaces:

- **List workspaces**: Paginated with search by name or slug
- **View workspace detail**: Settings, member list, group list, member count
- **Create workspace**: Create new workspaces with name, slug, and description
- **Update workspace**: Edit name and description
- **Delete workspace**: Remove workspace and all associated data (cascading delete)
- **Manage members**: Invite, change role, remove members
- **Manage groups**: Create, update, delete groups; add/remove group members

### Roles Management

Custom RBAC roles within workspaces (accessible from the workspace detail page, "Roles" tab):

- **List roles**: View all custom roles in a workspace with action and member counts
- **Create role**: Define a new named role with an optional description
- **Edit role**: Update role name and description
- **Delete role**: Remove a role and all its assignments
- **Manage role actions**: Add or remove service actions from a role (dropdown of all registered actions)
- **Manage role members**: Assign or remove workspace members from a role

### Service Actions Browser

A dedicated "Actions" page in the sidebar showing all registered service actions:

- **Grouped by service**: Each service displayed as a card with its actions in a table
- **Action details**: Action name, description, and registration date
- **Read-only**: Actions are registered by services, not created manually

### Permissions Browser

Browse and manage resource permissions across all workspaces:

- **List permissions**: Paginated, filterable by workspace and service name
- **View permission detail**: Resource info, owner, visibility, current shares
- **Update visibility**: Toggle between `private` and `workspace`
- **Manage shares**: Add or revoke shares for users and groups

### Activity Logs

A chronological feed of system events:

- User logins and admin logins
- User activations and deactivations
- Workspace creation, updates, and deletion
- Member invitations, role changes, and removals
- Group creation, updates, deletion, and membership changes
- Permission visibility changes and share modifications
- Role creation, updates, deletion, and membership changes
- Service action registration
- Role action additions and removals

Each log entry records the action, target type and ID, actor ID, workspace context (if applicable), and a detail payload with event-specific metadata.

## Authentication Flow

Admin authentication uses the same OAuth providers as regular user authentication, but with a separate callback flow that verifies admin status and issues an admin-specific JWT stored in a cookie.

```
1. Admin navigates to the admin panel login page
2. Admin clicks "Sign in with {provider}"
3. Browser → GET /auth/admin/login/{provider}
4. Sentinel redirects to OAuth provider
5. OAuth provider authenticates the user
6. Provider redirects to GET /auth/admin/callback/{provider}
7. Sentinel:
   a. Exchanges authorization code for tokens
   b. Extracts user info (same logic as regular auth)
   c. Calls find_or_create_user()
   d. Checks user.is_admin flag
   e. If not admin → redirect to login page with error=not_admin
   f. If admin → create admin JWT token
8. Sentinel sets admin_token cookie and redirects to admin panel
```

### Admin JWT Cookie

| Property | Value |
|----------|-------|
| Cookie name | `admin_token` |
| HttpOnly | Yes (not accessible via JavaScript) |
| SameSite | `Strict` |
| Secure | Configured via `COOKIE_SECURE` (set `True` in production) |
| Max age | 1 hour |
| Path | `/` |

The admin JWT contains:

```json
{
  "sub": "user-uuid",
  "email": "admin@example.com",
  "name": "Admin User",
  "admin": true,
  "iat": 1700000000,
  "exp": 1700028800,
  "type": "admin_access"
}
```

The `require_admin` dependency validates the cookie on every admin API request:

1. Read the `admin_token` cookie
2. Decode and verify the JWT signature and expiration
3. Check that the `admin` claim is `true`
4. Return the payload (or reject with `401`/`403`)

### Logout

```
POST /auth/admin/logout
```

Deletes the `admin_token` cookie. Since the cookie is HttpOnly, it cannot be cleared by client-side JavaScript -- the logout must go through the server endpoint.

## Configuring Admin Access

### ADMIN_EMAILS Environment Variable

The simplest way to grant admin access is through the `ADMIN_EMAILS` environment variable:

```
ADMIN_EMAILS=alice@example.com,bob@example.com
```

When a user logs in (via any provider) and their email matches an entry in this list, their `is_admin` flag is automatically set to `true`. This happens during the `find_or_create_user()` flow.

### Promoting Users via Script

For users who have already logged in and need to be promoted to admin:

```bash
make create-admin
```

This script connects to the database and sets `is_admin = true` for the specified user. It is useful for bootstrapping the first admin account or promoting users whose emails were not in the `ADMIN_EMAILS` list at the time they first logged in.

### Admin Panel URL

The admin panel URL is configured via:

```
ADMIN_URL=http://localhost:9004
```

This is used by Sentinel to redirect the admin after successful authentication. In production, set this to the public URL of the admin panel (e.g., `https://admin.identity.example.com`).

## API Endpoints

All admin endpoints are prefixed with `/admin` and require the `require_admin` dependency (valid admin JWT cookie).

| Category | Endpoint | Method | Description |
|----------|----------|--------|-------------|
| Stats | `/admin/stats` | GET | Dashboard statistics |
| Activity | `/admin/activity` | GET | Recent activity log (limit param) |
| Users | `/admin/users` | GET | Paginated user list |
| Users | `/admin/users/{id}` | GET | User detail |
| Users | `/admin/users/{id}` | PATCH | Update user |
| Users | `/admin/users/{id}/workspaces` | POST | Add user to workspace |
| Workspaces | `/admin/workspaces` | GET | Paginated workspace list |
| Workspaces | `/admin/workspaces` | POST | Create workspace |
| Workspaces | `/admin/workspaces/all` | GET | All workspaces (for dropdowns) |
| Workspaces | `/admin/workspaces/{id}` | GET | Workspace detail |
| Workspaces | `/admin/workspaces/{id}` | PATCH | Update workspace |
| Workspaces | `/admin/workspaces/{id}` | DELETE | Delete workspace |
| Members | `/admin/workspaces/{id}/members` | GET | List workspace members |
| Members | `/admin/workspaces/{id}/members/invite` | POST | Invite member |
| Members | `/admin/workspaces/{id}/members/{uid}` | PATCH | Change member role |
| Members | `/admin/workspaces/{id}/members/{uid}` | DELETE | Remove member |
| Groups | `/admin/workspaces/{id}/groups` | GET | List workspace groups |
| Groups | `/admin/workspaces/{id}/groups` | POST | Create group |
| Groups | `/admin/groups/{id}` | PATCH | Update group |
| Groups | `/admin/groups/{id}` | DELETE | Delete group |
| Groups | `/admin/groups/{id}/members` | GET | List group members |
| Groups | `/admin/groups/{id}/members/{uid}` | POST | Add group member |
| Groups | `/admin/groups/{id}/members/{uid}` | DELETE | Remove group member |
| Roles | `/admin/service-actions` | GET | List registered service actions |
| Roles | `/admin/workspaces/{id}/roles` | GET | List workspace roles |
| Roles | `/admin/workspaces/{id}/roles` | POST | Create role |
| Roles | `/admin/roles/{id}` | PATCH | Update role |
| Roles | `/admin/roles/{id}` | DELETE | Delete role |
| Roles | `/admin/roles/{id}/actions` | GET | List role actions |
| Roles | `/admin/roles/{id}/actions` | POST | Add actions to role |
| Roles | `/admin/roles/{id}/actions/{said}` | DELETE | Remove action from role |
| Roles | `/admin/roles/{id}/members` | GET | List role members |
| Roles | `/admin/roles/{id}/members/{uid}` | POST | Assign user to role |
| Roles | `/admin/roles/{id}/members/{uid}` | DELETE | Remove user from role |
| Permissions | `/admin/permissions` | GET | Paginated permission list |
| Permissions | `/admin/permissions/{id}` | GET | Permission detail |
| Permissions | `/admin/permissions/{id}/visibility` | PATCH | Update visibility |
| Permissions | `/admin/permissions/{id}/share` | POST | Create share |
| Permissions | `/admin/permissions/{id}/share` | DELETE | Revoke share |
| CSV Import | `/admin/import/csv/preview` | POST | Preview CSV import |
| CSV Import | `/admin/import/csv/execute` | POST | Execute CSV import |
