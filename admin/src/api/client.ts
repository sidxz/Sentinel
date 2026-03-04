import type {
  ActivityLog,
  AdminResourcePermission,
  CsvImportPreview,
  CsvImportResult,
  Group,
  GroupMember,
  PaginatedResponse,
  Stats,
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
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function upload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}${path}`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
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

export const getActivity = (limit = 20) =>
  request<ActivityLog[]>(`/admin/activity?limit=${limit}`);

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

export const updateUser = (id: string, body: { name?: string; is_active?: boolean }) =>
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

export const adminListPermissions = (
  page = 1,
  pageSize = 20,
  workspaceId?: string,
  serviceName?: string,
) => {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (workspaceId) params.set("workspace_id", workspaceId);
  if (serviceName) params.set("service_name", serviceName);
  return request<PaginatedResponse<AdminResourcePermission>>(
    `/admin/permissions?${params}`
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

// ── CSV Import ───────────────────────────────────────────────────────

export const csvPreview = (file: File) =>
  upload<CsvImportPreview>("/admin/import/csv/preview", file);

export const csvExecute = (file: File) =>
  upload<CsvImportResult>("/admin/import/csv/execute", file);
