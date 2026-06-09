"""Admin CRUD + guards for organizations, domains, and workspace allowed-orgs.

Kept separate from organization_service.py (the hot-path resolution/enforcement
module used on every sign-in). Raises typed exceptions the routes map to HTTP:
OrgNotFound -> 404, OrgConflict -> 409, OrgProtected -> 400.
"""

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import (
    Organization,
    OrganizationDomain,
    WorkspaceAllowedOrganization,
)
from src.models.user import User
from src.models.workspace import Workspace
from src.services import organization_service


class OrgNotFound(Exception):
    """Organization / domain / workspace does not exist."""


class OrgConflict(Exception):
    """Slug or domain already in use."""


class OrgProtected(Exception):
    """Operation not allowed on the public organization."""


async def create_organization(
    db: AsyncSession, name: str, slug: str
) -> Organization:
    taken = (
        await db.execute(select(Organization.id).where(Organization.slug == slug))
    ).scalar_one_or_none()
    if taken is not None:
        raise OrgConflict(f"Organization slug {slug!r} is already in use")
    org = Organization(name=name, slug=slug, is_public=False, enabled=True)
    db.add(org)
    await db.flush()
    return org


async def update_organization(
    db: AsyncSession,
    org_id: uuid.UUID,
    name: str | None = None,
    enabled: bool | None = None,
) -> Organization:
    org = await db.get(Organization, org_id)
    if org is None:
        raise OrgNotFound("Organization not found")
    if name is not None:
        org.name = name
    if enabled is not None:
        org.enabled = enabled
    await db.flush()
    return org


async def delete_organization(db: AsyncSession, org_id: uuid.UUID) -> None:
    org = await db.get(Organization, org_id)
    if org is None:
        raise OrgNotFound("Organization not found")
    if org.is_public:
        raise OrgProtected("The public organization cannot be deleted")
    await db.delete(org)
    await db.flush()


async def list_organizations(db: AsyncSession) -> list[dict]:
    """List orgs with domain + user counts; public org sorted first."""
    dc = (
        select(
            OrganizationDomain.organization_id.label("oid"),
            func.count().label("c"),
        )
        .group_by(OrganizationDomain.organization_id)
        .subquery()
    )
    uc = (
        select(User.organization_id.label("oid"), func.count().label("c"))
        .group_by(User.organization_id)
        .subquery()
    )
    stmt = (
        select(
            Organization,
            func.coalesce(dc.c.c, 0),
            func.coalesce(uc.c.c, 0),
        )
        .outerjoin(dc, dc.c.oid == Organization.id)
        .outerjoin(uc, uc.c.oid == Organization.id)
        .order_by(Organization.is_public.desc(), Organization.name)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {"org": org, "domain_count": d, "user_count": u} for org, d, u in rows
    ]


async def get_organization_detail(
    db: AsyncSession, org_id: uuid.UUID
) -> dict | None:
    org = await db.get(Organization, org_id)
    if org is None:
        return None
    domains = (
        (
            await db.execute(
                select(OrganizationDomain)
                .where(OrganizationDomain.organization_id == org_id)
                .order_by(OrganizationDomain.domain)
            )
        )
        .scalars()
        .all()
    )
    user_count = (
        await db.execute(
            select(func.count()).where(User.organization_id == org_id)
        )
    ).scalar_one()
    return {"org": org, "domains": list(domains), "user_count": user_count}
