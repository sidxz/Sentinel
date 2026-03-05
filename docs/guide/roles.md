# Custom Roles (RBAC)

The Daikon Identity Service implements NIST Core RBAC (Level 1) as a third authorization layer between workspace roles and entity ACLs. Custom roles allow services to define application-specific actions (like "export reports" or "manage templates") and assign them to users through named roles within a workspace.

## Three-Tier Authorization Model

```
Workspace Roles (JWT)     →  coarse tier: owner/admin/editor/viewer
Custom Roles (API check)  →  action-based: "can user do reports:export?"
Entity ACLs (Zanzibar)    →  per-resource: "can user edit document X?"
```

| Tier | Storage | Check Speed | Use Case |
|------|---------|-------------|----------|
| Workspace Roles | JWT claims | Instant (local) | Broad access control (create, manage, delete) |
| Custom Roles | Database query | Sub-millisecond | Action-based authorization (export, approve, configure) |
| Entity ACLs | Database query | Sub-millisecond | Per-resource access (view doc X, edit project Y) |

## Concepts

### Service Actions

Service actions are the atomic units of authorization. Each action belongs to a `service_name` and has a unique `action` identifier. Actions are registered by backend services using service-key authentication.

**Action naming convention:** `^[a-z][a-z0-9_.:-]*$`

Examples:
- `reports:export`
- `templates:manage`
- `billing:view`
- `settings:admin.configure`

### Roles

Roles are workspace-scoped collections of service actions. They are created by workspace admins (or platform admins via the admin panel) and can contain actions from multiple services.

Example roles:
- **Analyst**: `reports:export`, `reports:view`, `dashboards:view`
- **Template Manager**: `templates:create`, `templates:edit`, `templates:delete`
- **Billing Admin**: `billing:view`, `billing:manage`, `invoices:export`

### User Role Assignments

Users are assigned to roles within a workspace. A user can have multiple roles, and the effective set of allowed actions is the union of all their role assignments.

## Security Properties

- **Workspace-scoped only**: Roles exist only within a workspace -- no global roles. This maintains tenant isolation.
- **Namespaced actions**: Actions are scoped by `service_name` to prevent namespace collisions between services.
- **Registered actions only**: Actions must be pre-registered by services (using service-key auth) before they can be added to roles. This prevents privilege escalation through invented action names.
- **Real-time checks**: Action checks are always live database queries, never cached in JWTs. Revoking a role takes effect immediately.
- **CASCADE delete**: Deleting a workspace removes all its roles and user assignments. Deleting a user removes all their role assignments.

## Workflow

### 1. Service Registers Actions

When your service starts up (or during deployment), register the actions it supports:

```
POST /roles/actions/register
X-Service-Key: sk_your_service_key

{
  "service_name": "analytics",
  "actions": [
    {"action": "reports:export", "description": "Export reports as CSV/PDF"},
    {"action": "reports:view", "description": "View report data"},
    {"action": "dashboards:create", "description": "Create new dashboards"}
  ]
}
```

Registration is idempotent -- re-registering existing actions updates their descriptions without creating duplicates.

### 2. Admin Creates Roles

Through the admin panel or API, create roles in a workspace and assign actions:

```
POST /admin/workspaces/{workspace_id}/roles
{
  "name": "Analyst",
  "description": "Can view and export reports"
}
```

Then add actions to the role:

```
POST /admin/roles/{role_id}/actions
{
  "service_action_ids": ["uuid-of-reports-export", "uuid-of-reports-view"]
}
```

### 3. Admin Assigns Users to Roles

```
POST /admin/roles/{role_id}/members/{user_id}
```

### 4. Service Checks Actions at Runtime

Using the SDK:

```python
from identity_sdk.roles import RoleClient

roles = RoleClient(
    base_url="http://identity-service:8000",
    service_name="analytics",
    service_key="sk_your_service_key",
)

# Check a single action
allowed = await roles.check_action(user_token, "reports:export", workspace_id)

# List all actions the user can perform
actions = await roles.get_user_actions(user_token, workspace_id)
# → ["reports:export", "reports:view"]
```

Or using the `require_action` dependency:

```python
from identity_sdk.dependencies import require_action

@router.get("/reports/export")
async def export_report(
    user: AuthenticatedUser = Depends(require_action(roles, "reports:export")),
):
    # User is guaranteed to have the reports:export action
    return generate_report()
```

## When to Use Each Tier

| Scenario | Tier |
|----------|------|
| "Can this user create resources?" | Workspace role (`require_role("editor")`) |
| "Can this user export reports?" | Custom role (`require_action(roles, "reports:export")`) |
| "Can this user view this specific document?" | Entity ACL (`permissions.can(token, "document", doc_id, "view")`) |

## Database Schema

Four tables support the RBAC system:

```
service_actions     -- Registry of valid actions per service
    ├── UNIQUE(service_name, action)
    └── INDEX(service_name)

roles               -- Custom roles per workspace
    ├── FK workspace_id → workspaces (CASCADE)
    ├── FK created_by → users (SET NULL)
    ├── UNIQUE(workspace_id, name)
    └── INDEX(workspace_id)

role_actions        -- Links roles to registered actions
    ├── FK role_id → roles (CASCADE)
    ├── FK service_action_id → service_actions (CASCADE)
    ├── UNIQUE(role_id, service_action_id)
    └── INDEX(role_id)

user_roles          -- User-to-role assignments
    ├── FK user_id → users (CASCADE)
    ├── FK role_id → roles (CASCADE)
    ├── FK assigned_by → users (SET NULL)
    ├── UNIQUE(user_id, role_id)
    └── INDEX(user_id), INDEX(role_id)
```

The core action check is a 4-table join that resolves in sub-millisecond time with the indexed foreign keys.
