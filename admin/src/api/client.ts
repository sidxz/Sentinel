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

// Admin
export const getStats = () => request<import("../types/api").Stats>("/admin/stats");

export const getUsers = (page = 1, pageSize = 20, search?: string) => {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (search) params.set("search", search);
  return request<import("../types/api").PaginatedResponse<import("../types/api").User>>(
    `/admin/users?${params}`
  );
};

export const getUserDetail = (id: string) =>
  request<import("../types/api").UserDetail>(`/admin/users/${id}`);

export const updateUser = (id: string, body: { name?: string; is_active?: boolean }) =>
  request<import("../types/api").UserDetail>(`/admin/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const getWorkspaces = (page = 1, pageSize = 20, search?: string) => {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (search) params.set("search", search);
  return request<import("../types/api").PaginatedResponse<import("../types/api").Workspace>>(
    `/admin/workspaces?${params}`
  );
};

// Workspace details (uses existing non-admin endpoints)
export const getWorkspace = (id: string) =>
  request<import("../types/api").Workspace>(`/workspaces/${id}`);

export const getWorkspaceMembers = (id: string) =>
  request<import("../types/api").WorkspaceMember[]>(`/workspaces/${id}/members`);

export const getWorkspaceGroups = (id: string) =>
  request<import("../types/api").Group[]>(`/workspaces/${id}/groups`);

export const inviteMember = (workspaceId: string, email: string, role = "viewer") =>
  request(`/workspaces/${workspaceId}/members/invite`, {
    method: "POST",
    body: JSON.stringify({ email, role }),
  });

export const updateMemberRole = (workspaceId: string, userId: string, role: string) =>
  request(`/workspaces/${workspaceId}/members/${userId}`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });

export const removeMember = (workspaceId: string, userId: string) =>
  request(`/workspaces/${workspaceId}/members/${userId}`, { method: "DELETE" });
