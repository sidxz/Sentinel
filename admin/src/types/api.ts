export interface User {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  is_active: boolean;
  created_at: string;
  workspace_count: number;
}

export interface UserDetail extends Omit<User, "workspace_count"> {
  updated_at: string;
  social_accounts: SocialAccount[];
  memberships: UserMembership[];
}

export interface SocialAccount {
  id: string;
  provider: string;
  provider_user_id: string;
}

export interface UserMembership {
  workspace_id: string;
  workspace_name: string;
  workspace_slug: string;
  role: string;
  joined_at: string;
}

export interface Workspace {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  created_by: string;
  created_at: string;
  member_count: number;
}

export interface WorkspaceMember {
  user_id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  role: string;
  joined_at: string;
}

export interface Group {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  created_by: string;
  created_at: string;
}

export interface GroupMember {
  user_id: string;
  email: string;
  name: string;
  added_at: string;
}

export interface ResourcePermission {
  id: string;
  service_name: string;
  resource_type: string;
  resource_id: string;
  workspace_id: string;
  owner_id: string;
  visibility: string;
  created_at: string;
  shares: ResourceShare[];
}

export interface ResourceShare {
  id: string;
  grantee_type: string;
  grantee_id: string;
  permission: string;
  granted_by: string;
  granted_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Stats {
  total_users: number;
  total_workspaces: number;
  total_groups: number;
  total_resources: number;
  recent_users: User[];
}
