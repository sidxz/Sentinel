import type {
  ActivityLog,
  AdminResourcePermission,
  ClientApp,
  CsvImportPreview,
  CsvImportResult,
  CustomRole,
  Group,
  GroupMember,
  PaginatedResponse,
  RoleMember,
  ServiceAction,
  ServiceApp,
  ServiceAppCreateResponse,
  Stats,
  SystemHealth,
  SystemSettings,
  User,
  UserDetail,
  Workspace,
  WorkspaceDetail,
  WorkspaceMember,
  WorkspaceOption,
} from "../types/api";

const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
      ...options?.headers,
    },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((e: { msg?: string }) => e.msg ?? JSON.stringify(e)).join("; ")
          : `HTTP ${res.status}`;
    throw new Error(message);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

async function upload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    body: form,
    headers: { "X-Requested-With": "XMLHttpRequest" },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((e: { msg?: string }) => e.msg ?? JSON.stringify(e)).join("; ")
          : `HTTP ${res.status}`;
    throw new Error(message);
  }
  return res.json();
}

// Auth
export const getAdminMe = () =>
  request<{ id: string; email: string; name: string }>("/auth/admin/me");

export const getAuthProviders = () =>
  request<{ providers: string[] }>("/auth/providers");

export const adminLogout = () =>
  request("/auth/admin/logout", { method: "POST" });

// ── Admin Stats & Dashboard ──────────────────────────────────────────

export const getStats = () => request<Stats>("/admin/stats");

export const getActivity = (params: {
  page?: number;
  page_size?: number;
  action?: string;
  target_type?: string;
  workspace_id?: string;
  actor_id?: string;
  from_date?: string;
  to_date?: string;
} = {}) => {
  const p = new URLSearchParams();
  p.set("page", String(params.page ?? 1));
  p.set("page_size", String(params.page_size ?? 20));
  if (params.action) p.set("action", params.action);
  if (params.target_type) p.set("target_type", params.target_type);
  if (params.workspace_id) p.set("workspace_id", params.workspace_id);
  if (params.actor_id) p.set("actor_id", params.actor_id);
  if (params.from_date) p.set("from_date", params.from_date);
  if (params.to_date) p.set("to_date", params.to_date);
  return request<PaginatedResponse<ActivityLog>>(`/admin/activity?${p}`);
};

export const getAllWorkspaces = () =>
  request<WorkspaceOption[]>("/admin/workspaces/all");

// ── Users ────────────────────────────────────────────────────────────

export const getUsers = (page = 1, pageSize = 20, search?: string) => {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (search) params.set("search", search);
  return request<PaginatedResponse<User>>(`/admin/users?${params}`);
};

export const getUserDetail = (id: string) =>
  request<UserDetail>(`/admin/users/${id}`);

export const updateUser = (id: string, body: { name?: string; is_active?: boolean; is_admin?: boolean }) =>
  request<UserDetail>(`/admin/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const addUserToWorkspace = (userId: string, workspaceId: string, role: string) =>
  request(`/admin/users/${userId}/workspaces`, {
    method: "POST",
    body: JSON.stringify({ workspace_id: workspaceId, role }),
  });

// ── Workspaces ───────────────────────────────────────────────────────

export const getWorkspaces = (page = 1, pageSize = 20, search?: string) => {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (search) params.set("search", search);
  return request<PaginatedResponse<Workspace>>(`/admin/workspaces?${params}`);
};

export const createWorkspace = (body: { name: string; slug: string; description?: string }) =>
  request<WorkspaceDetail>("/admin/workspaces", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getWorkspace = (id: string) =>
  request<WorkspaceDetail>(`/admin/workspaces/${id}`);

export const updateWorkspace = (id: string, body: { name?: string; description?: string }) =>
  request<WorkspaceDetail>(`/admin/workspaces/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const deleteWorkspace = (id: string) =>
  request(`/admin/workspaces/${id}`, { method: "DELETE" });

// ── Workspace Members ────────────────────────────────────────────────

export const getWorkspaceMembers = (id: string) =>
  request<WorkspaceMember[]>(`/admin/workspaces/${id}/members`);

export const inviteMember = (workspaceId: string, email: string, role = "viewer") =>
  request(`/admin/workspaces/${workspaceId}/members/invite`, {
    method: "POST",
    body: JSON.stringify({ email, role }),
  });

export const updateMemberRole = (workspaceId: string, userId: string, role: string) =>
  request(`/admin/workspaces/${workspaceId}/members/${userId}`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });

export const removeMember = (workspaceId: string, userId: string) =>
  request(`/admin/workspaces/${workspaceId}/members/${userId}`, { method: "DELETE" });

// ── Groups ───────────────────────────────────────────────────────────

export const getWorkspaceGroups = (workspaceId: string) =>
  request<Group[]>(`/admin/workspaces/${workspaceId}/groups`);

export const createGroup = (workspaceId: string, body: { name: string; description?: string }) =>
  request<Group>(`/admin/workspaces/${workspaceId}/groups`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const updateGroup = (groupId: string, body: { name?: string; description?: string }) =>
  request<Group>(`/admin/groups/${groupId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const deleteGroup = (groupId: string) =>
  request(`/admin/groups/${groupId}`, { method: "DELETE" });

export const getGroupMembers = (groupId: string) =>
  request<GroupMember[]>(`/admin/groups/${groupId}/members`);

export const addGroupMember = (groupId: string, userId: string) =>
  request(`/admin/groups/${groupId}/members/${userId}`, { method: "POST" });

export const removeGroupMember = (groupId: string, userId: string) =>
  request(`/admin/groups/${groupId}/members/${userId}`, { method: "DELETE" });

// ── Permissions ──────────────────────────────────────────────────────

export const adminListPermissions = (params: {
  page?: number;
  pageSize?: number;
  workspaceId?: string;
  serviceName?: string;
  resourceId?: string;
  owner?: string;
  sortBy?: string;
  sortOrder?: string;
} = {}) => {
  const p = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.pageSize ?? 20),
  });
  if (params.workspaceId) p.set("workspace_id", params.workspaceId);
  if (params.serviceName) p.set("service_name", params.serviceName);
  if (params.resourceId) p.set("resource_id", params.resourceId);
  if (params.owner) p.set("owner", params.owner);
  if (params.sortBy) p.set("sort_by", params.sortBy);
  if (params.sortOrder) p.set("sort_order", params.sortOrder);
  return request<PaginatedResponse<AdminResourcePermission>>(
    `/admin/permissions?${p}`
  );
};

export const adminGetPermission = (id: string) =>
  request<AdminResourcePermission>(`/admin/permissions/${id}`);

export const adminUpdateVisibility = (permissionId: string, visibility: string) =>
  request(`/admin/permissions/${permissionId}/visibility`, {
    method: "PATCH",
    body: JSON.stringify({ visibility }),
  });

export const adminSharePermission = (
  permissionId: string,
  body: { grantee_type: string; grantee_id: string; permission: string },
) =>
  request(`/admin/permissions/${permissionId}/share`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const adminRevokeShare = (
  permissionId: string,
  granteeType: string,
  granteeId: string,
) =>
  request(
    `/admin/permissions/${permissionId}/share?grantee_type=${granteeType}&grantee_id=${granteeId}`,
    { method: "DELETE" },
  );

// ── Roles (RBAC) ────────────────────────────────────────────────────

export const getServiceActions = (serviceName?: string) => {
  const params = new URLSearchParams();
  if (serviceName) params.set("service_name", serviceName);
  const qs = params.toString();
  return request<ServiceAction[]>(`/admin/service-actions${qs ? `?${qs}` : ""}`);
};

export const deleteServiceAction = (id: string) =>
  request(`/admin/service-actions/${id}`, { method: "DELETE" });

export const getWorkspaceRoles = (workspaceId: string) =>
  request<CustomRole[]>(`/admin/workspaces/${workspaceId}/roles`);

export const createRole = (workspaceId: string, body: { name: string; description?: string }) =>
  request<CustomRole>(`/admin/workspaces/${workspaceId}/roles`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const updateRole = (roleId: string, body: { name?: string; description?: string }) =>
  request<CustomRole>(`/admin/roles/${roleId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const deleteRole = (roleId: string) =>
  request(`/admin/roles/${roleId}`, { method: "DELETE" });

export const getRoleActions = (roleId: string) =>
  request<ServiceAction[]>(`/admin/roles/${roleId}/actions`);

export const addRoleActions = (roleId: string, serviceActionIds: string[]) =>
  request(`/admin/roles/${roleId}/actions`, {
    method: "POST",
    body: JSON.stringify({ service_action_ids: serviceActionIds }),
  });

export const removeRoleAction = (roleId: string, serviceActionId: string) =>
  request(`/admin/roles/${roleId}/actions/${serviceActionId}`, { method: "DELETE" });

export const getRoleMembers = (roleId: string) =>
  request<RoleMember[]>(`/admin/roles/${roleId}/members`);

export const addRoleMember = (roleId: string, userId: string) =>
  request(`/admin/roles/${roleId}/members/${userId}`, { method: "POST" });

export const removeRoleMember = (roleId: string, userId: string) =>
  request(`/admin/roles/${roleId}/members/${userId}`, { method: "DELETE" });

// ── Client Apps ─────────────────────────────────────────────────────

export const getClientApps = () =>
  request<ClientApp[]>("/admin/client-apps");

export const createClientApp = (body: { name: string; redirect_uris: string[] }) =>
  request<ClientApp>("/admin/client-apps", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getClientApp = (id: string) =>
  request<ClientApp>(`/admin/client-apps/${id}`);

export const updateClientApp = (
  id: string,
  body: { name?: string; redirect_uris?: string[]; is_active?: boolean; revoke_sessions?: boolean },
) =>
  request<ClientApp>(`/admin/client-apps/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const deleteClientApp = (id: string) =>
  request(`/admin/client-apps/${id}`, { method: "DELETE" });

// ── Service Apps ────────────────────────────────────────────────────

export const getServiceApps = () =>
  request<ServiceApp[]>("/admin/service-apps");

export const createServiceApp = (body: {
  name: string;
  service_name: string;
  allowed_origins?: string[];
}) =>
  request<ServiceAppCreateResponse>("/admin/service-apps", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getServiceApp = (id: string) =>
  request<ServiceApp>(`/admin/service-apps/${id}`);

export const updateServiceApp = (
  id: string,
  body: { name?: string; is_active?: boolean; allowed_origins?: string[] },
) =>
  request<ServiceApp>(`/admin/service-apps/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const rotateServiceAppKey = (id: string) =>
  request<ServiceAppCreateResponse>(`/admin/service-apps/${id}/rotate-key`, {
    method: "POST",
  });

export const deleteServiceApp = (id: string) =>
  request(`/admin/service-apps/${id}`, { method: "DELETE" });

// ── CSV Import ───────────────────────────────────────────────────────

export const csvPreview = (file: File) =>
  upload<CsvImportPreview>("/admin/import/csv/preview", file);

export const csvExecute = (file: File) =>
  upload<CsvImportResult>("/admin/import/csv/execute", file);

// ── System ──────────────────────────────────────────────────────────

export const getSystemHealth = () =>
  request<SystemHealth>("/admin/system/health");

export const getSystemSettings = () =>
  request<SystemSettings>("/admin/system/settings");

// ── Token Management ────────────────────────────────────────────────

export const revokeUserTokens = (userId: string) =>
  request<{ status: string; tokens_revoked: number }>(
    `/admin/users/${userId}/revoke-tokens`,
    { method: "POST" },
  );

// ── Bulk Operations ─────────────────────────────────────────────────

export const bulkUserStatus = (userIds: string[], isActive: boolean) =>
  request<{ status: string; affected: number }>("/admin/users/bulk-status", {
    method: "POST",
    body: JSON.stringify({ user_ids: userIds, is_active: isActive }),
  });

// ── Data Export ─────────────────────────────────────────────────────

async function downloadCsv(path: string, filename: string) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const exportUsers = () => downloadCsv("/admin/export/users", "users.csv");
export const exportWorkspaces = () => downloadCsv("/admin/export/workspaces", "workspaces.csv");
