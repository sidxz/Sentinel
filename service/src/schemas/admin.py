import uuid
from datetime import datetime

from pydantic import BaseModel


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    avatar_url: str | None
    is_active: bool
    created_at: datetime
    workspace_count: int

    model_config = {"from_attributes": True}


class AdminUserDetailResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    avatar_url: str | None
    is_active: bool
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


class AdminWorkspaceResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    created_by: uuid.UUID
    created_at: datetime
    member_count: int

    model_config = {"from_attributes": True}


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
    recent_users: list[AdminUserResponse]
