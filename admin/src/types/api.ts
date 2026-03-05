export interface User {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  is_active: boolean;
  is_admin: boolean;
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

export interface WorkspaceDetail extends Workspace {
  group_count: number;
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

export interface AdminResourcePermission {
  id: string;
  service_name: string;
  resource_type: string;
  resource_id: string;
  workspace_id: string;
  owner_id: string;
  owner_email: string | null;
  visibility: string;
  created_at: string;
  share_count: number;
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

// ── RBAC ────────────────────────────────────────────────────────────

export interface ServiceAction {
  id: string;
  service_name: string;
  action: string;
  description: string | null;
  created_at: string;
}

export interface CustomRole {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  created_by: string | null;
  created_at: string;
  action_count: number;
  member_count: number;
}

export interface RoleMember {
  user_id: string;
  email: string;
  name: string;
  assigned_at: string;
  assigned_by: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface TopWorkspace {
  id: string;
  name: string;
  slug: string;
  member_count: number;
}

export interface WorkspaceOption {
  id: string;
  name: string;
  slug: string;
}

export interface Stats {
  total_users: number;
  total_workspaces: number;
  total_groups: number;
  total_resources: number;
  active_users: number;
  inactive_users: number;
  recent_users: User[];
  top_workspaces: TopWorkspace[];
}

export interface ActivityLog {
  id: string;
  action: string;
  actor_id: string | null;
  actor_name: string | null;
  actor_email: string | null;
  target_type: string;
  target_id: string;
  workspace_id: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export interface CsvImportRow {
  email: string;
  name: string;
  workspace_slug: string;
  role: string;
  error: string | null;
}

export interface CsvImportPreview {
  rows: CsvImportRow[];
  valid_count: number;
  error_count: number;
}

export interface CsvImportResult {
  users_created: number;
  memberships_added: number;
  errors: string[];
}

// ── Client Apps ─────────────────────────────────────────────────────

export interface ClientApp {
  id: string;
  name: string;
  redirect_uris: string[];
  is_active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

// ── System Health ───────────────────────────────────────────────────

export interface HealthCheckDetail {
  status: string;
  latency_ms: number;
  error: string | null;
}

export interface SystemHealth {
  status: string;
  checks: Record<string, HealthCheckDetail>;
  uptime_seconds: number;
  version: string;
}

// ── Settings ────────────────────────────────────────────────────────

export interface OAuthProviderInfo {
  name: string;
  configured: boolean;
}

export interface JwtInfo {
  algorithm: string;
  access_token_expire_minutes: number;
  refresh_token_expire_days: number;
  public_key_preview: string;
  denylist_count: number;
}

export interface SecurityInfo {
  cookie_secure: boolean;
  allowed_hosts: string[];
  cors_origins: string[];
  session_secret_configured: boolean;
  admin_emails: string[];
}

export interface RateLimitInfo {
  endpoint: string;
  limit: string;
}

export interface ServiceKeyInfo {
  name: string;
  preview: string;
}

export interface ServiceInfoType {
  base_url: string;
  frontend_url: string;
  admin_url: string;
}

export interface SystemSettings {
  oauth_providers: OAuthProviderInfo[];
  jwt: JwtInfo;
  security: SecurityInfo;
  rate_limits: RateLimitInfo[];
  service_keys: ServiceKeyInfo[];
  service: ServiceInfoType;
}
