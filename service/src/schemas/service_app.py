import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from src.schemas.validators import SafeStr, SafeStrOptional


class ServiceAppCreateRequest(BaseModel):
    name: SafeStr = Field(min_length=1, max_length=255)
    service_name: str = Field(
        pattern=r"^[a-z][a-z0-9-]*[a-z0-9]$", min_length=2, max_length=255
    )


class ServiceAppUpdateRequest(BaseModel):
    name: SafeStrOptional = None
    is_active: bool | None = None


class ServiceAppResponse(BaseModel):
    id: uuid.UUID
    name: str
    service_name: str
    key_prefix: str
    is_active: bool
    last_used_at: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ServiceAppCreateResponse(ServiceAppResponse):
    api_key: str
