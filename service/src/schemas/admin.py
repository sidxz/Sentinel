import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    avatar_url: str | None
    is_active: bool
    is_admin: bool
    created_at: datetime
    workspace_count: int

    model_config = {"from_attributes": True}


class AdminUserDetailResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    avatar_url: str | None
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime
    social_accounts: list["SocialAccountResponse"]
    memberships: list["UserMembershipResponse"]

    model_config = {"from_attributes": True}


class SocialAccountResponse(BaseModel):
    id: uuid.UUID
    provider: str
    provider_user_id: str

    model_config = {"from_attributes": True}


class UserMembershipResponse(BaseModel):
    workspace_id: uuid.UUID
    workspace_name: str
    workspace_slug: str
    role: str
    joined_at: datetime


class AdminUserUpdateRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    is_admin: bool | None = None


class AdminWorkspaceResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    created_by: uuid.UUID
    created_at: datetime
    member_count: int

    model_config = {"from_attributes": True}


class AdminWorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    description: str | None = None


class AdminWorkspaceDetailResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    created_by: uuid.UUID
    created_at: datetime
    member_count: int
    group_count: int

    model_config = {"from_attributes": True}


class AdminAddUserToWorkspaceRequest(BaseModel):
    workspace_id: uuid.UUID
    role: str = Field(default="viewer", pattern=r"^(owner|admin|editor|viewer)$")


class AdminResourcePermissionResponse(BaseModel):
    id: uuid.UUID
    service_name: str
    resource_type: str
    resource_id: uuid.UUID
    workspace_id: uuid.UUID
    owner_id: uuid.UUID
    owner_email: str | None = None
    visibility: str
    created_at: datetime
    share_count: int = 0
    shares: list["AdminResourceShareResponse"] = []


class AdminResourceShareResponse(BaseModel):
    id: uuid.UUID
    grantee_type: str
    grantee_id: uuid.UUID
    permission: str
    granted_by: uuid.UUID
    granted_at: datetime


class CsvImportRow(BaseModel):
    email: str
    name: str
    workspace_slug: str
    role: str = "viewer"
    error: str | None = None


class CsvImportPreview(BaseModel):
    rows: list[CsvImportRow]
    valid_count: int
    error_count: int


class CsvImportResult(BaseModel):
    users_created: int
    memberships_added: int
    errors: list[str]


class ActivityLogResponse(BaseModel):
    id: uuid.UUID
    action: str
    actor_id: uuid.UUID | None
    actor_name: str | None
    actor_email: str | None
    target_type: str
    target_id: uuid.UUID
    workspace_id: uuid.UUID | None
    detail: dict | None
    created_at: datetime


class TopWorkspace(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    member_count: int


class WorkspaceOption(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


class AdminStatsResponse(BaseModel):
    total_users: int
    total_workspaces: int
    total_groups: int
    total_resources: int
    active_users: int
    inactive_users: int
    recent_users: list[AdminUserResponse]
    top_workspaces: list[TopWorkspace]


# ── Health ───────────────────────────────────────────────────────────

class HealthCheckDetail(BaseModel):
    status: str
    latency_ms: float
    error: str | None = None


class SystemHealthResponse(BaseModel):
    status: str  # "healthy" | "degraded"
    checks: dict[str, HealthCheckDetail]
    uptime_seconds: float
    version: str


# ── Settings ─────────────────────────────────────────────────────────

class OAuthProviderInfo(BaseModel):
    name: str
    configured: bool


class JwtInfo(BaseModel):
    algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    public_key_preview: str
    denylist_count: int


class SecurityInfo(BaseModel):
    cookie_secure: bool
    allowed_hosts: list[str]
    cors_origins: list[str]
    session_secret_configured: bool
    admin_emails: list[str]


class RateLimitInfo(BaseModel):
    endpoint: str
    limit: str


class ServiceKeyInfo(BaseModel):
    name: str
    preview: str


class ServiceInfo(BaseModel):
    base_url: str
    frontend_url: str
    admin_url: str


class SystemSettingsResponse(BaseModel):
    oauth_providers: list[OAuthProviderInfo]
    jwt: JwtInfo
    security: SecurityInfo
    rate_limits: list[RateLimitInfo]
    service_keys: list[ServiceKeyInfo]
    service: ServiceInfo


# ── Bulk Operations ──────────────────────────────────────────────────

class BulkUserStatusRequest(BaseModel):
    user_ids: list[uuid.UUID]
    is_active: bool
