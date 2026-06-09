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


async def create_organization(db: AsyncSession, name: str, slug: str) -> Organization:
    # DB unique constraint on slug is the concurrency backstop; this pre-check
    # just yields a cleaner error in the common (non-racing) case.
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
    return [{"org": org, "domain_count": d, "user_count": u} for org, d, u in rows]


async def get_organization_detail(db: AsyncSession, org_id: uuid.UUID) -> dict | None:
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
        await db.execute(select(func.count()).where(User.organization_id == org_id))
    ).scalar_one()
    return {"org": org, "domains": list(domains), "user_count": user_count}


async def add_domain(
    db: AsyncSession,
    org_id: uuid.UUID,
    domain: str,
    include_subdomains: bool,
) -> OrganizationDomain:
    org = await db.get(Organization, org_id)
    if org is None:
        raise OrgNotFound("Organization not found")
    if org.is_public:
        raise OrgProtected(
            "The public organization is the catch-all and cannot have domains"
        )
    normalized = organization_service.normalize_domain(domain)
    if normalized is None:
        raise ValueError(f"Invalid domain: {domain!r}")
    taken = (
        await db.execute(
            select(OrganizationDomain.id).where(OrganizationDomain.domain == normalized)
        )
    ).scalar_one_or_none()
    if taken is not None:
        raise OrgConflict(
            f"Domain {normalized!r} is already claimed by an organization"
        )
    row = OrganizationDomain(
        organization_id=org_id,
        domain=normalized,
        include_subdomains=include_subdomains,
    )
    db.add(row)
    await db.flush()
    return row


async def remove_domain(
    db: AsyncSession, org_id: uuid.UUID, domain_id: uuid.UUID
) -> None:
    row = await db.get(OrganizationDomain, domain_id)
    if row is None or row.organization_id != org_id:
        raise OrgNotFound("Domain not found")
    await db.delete(row)
    await db.flush()


async def get_workspace_allowed_orgs(
    db: AsyncSession, workspace_id: uuid.UUID
) -> list[Organization]:
    stmt = (
        select(Organization)
        .join(
            WorkspaceAllowedOrganization,
            WorkspaceAllowedOrganization.organization_id == Organization.id,
        )
        .where(WorkspaceAllowedOrganization.workspace_id == workspace_id)
        .order_by(Organization.name)
    )
    return list((await db.execute(stmt)).scalars().all())


async def set_workspace_allowed_orgs(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    organization_ids: list[uuid.UUID],
) -> None:
    """Replace the workspace's allowed-org set. Empty list = open to all."""
    workspace = await db.get(Workspace, workspace_id)
    if workspace is None:
        raise OrgNotFound("Workspace not found")
    ids = list(dict.fromkeys(organization_ids))  # dedupe, keep order
    if ids:
        found = set(
            (await db.execute(select(Organization.id).where(Organization.id.in_(ids))))
            .scalars()
            .all()
        )
        missing = [i for i in ids if i not in found]
        if missing:
            raise ValueError(f"Unknown organization ids: {[str(m) for m in missing]}")
    await db.execute(
        delete(WorkspaceAllowedOrganization).where(
            WorkspaceAllowedOrganization.workspace_id == workspace_id
        )
    )
    for oid in ids:
        db.add(
            WorkspaceAllowedOrganization(workspace_id=workspace_id, organization_id=oid)
        )
    await db.flush()


async def list_org_users(
    db: AsyncSession, org_id: uuid.UUID, limit: int = 50, offset: int = 0
) -> tuple[list[User], int]:
    total = (
        await db.execute(select(func.count()).where(User.organization_id == org_id))
    ).scalar_one()
    users = (
        (
            await db.execute(
                select(User)
                .where(User.organization_id == org_id)
                .order_by(User.email)
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return list(users), total
