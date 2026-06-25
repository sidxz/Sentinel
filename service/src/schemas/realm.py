"""Schemas for realm self-discovery (whoami) and no-user m2m token minting."""

from pydantic import BaseModel, Field


class RealmInfo(BaseModel):
    slug: str
    name: str


class WhoamiResponse(BaseModel):
    """What a service key resolves to: its own name, the shared ``effective_scope``
    it reads/writes permissions under, and its realm (null when standalone)."""

    service_name: str
    effective_scope: str
    realm: RealmInfo | None = None


class M2MTokenRequest(BaseModel):
    target: str | None = Field(
        default=None,
        description=(
            "Reserved for future per-call audience narrowing — NOT enforced in v1. "
            "When honored, restricts the token to a single target service_name."
        ),
    )


class M2MTokenResponse(BaseModel):
    token: str
    expires_in: int
