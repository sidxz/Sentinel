import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import (
    Organization,
    OrganizationDomain,
    WorkspaceAllowedOrganization,
)


def normalize_domain(value: str | None) -> str | None:
    """Extract and normalize the domain from an email or bare domain.

    Lowercases, strips, takes the part after a single '@' (if present),
    IDNA-encodes unicode labels, and returns None for anything malformed
    (empty, multiple '@', no dot, leading/trailing dot). This keys org lookups,
    so it must fail closed.
    """
    if not value:
        return None
    candidate = value.strip().lower()
    if candidate.count("@") > 1:
        return None
    if "@" in candidate:
        candidate = candidate.split("@", 1)[1]
    if not candidate or "." not in candidate:
        return None
    if candidate.startswith(".") or candidate.endswith("."):
        return None
    try:
        candidate = candidate.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return None
    return candidate


def match_org_id(
    domain: str,
    rows: list[tuple[uuid.UUID, str, bool]],
) -> uuid.UUID | None:
    """Pure resolver over (org_id, rule_domain, include_subdomains) rows from
    *enabled* orgs. Exact match is authoritative; otherwise the most specific
    (longest) subdomain rule whose pattern the domain is a sub-label of wins.
    """
    best_id: uuid.UUID | None = None
    best_len = -1
    for org_id, rule_domain, include_subdomains in rows:
        rule = rule_domain.lower()
        if domain == rule:
            return org_id
        if include_subdomains and domain.endswith("." + rule) and len(rule) > best_len:
            best_len = len(rule)
            best_id = org_id
    return best_id


async def resolve_organization(db: AsyncSession, email: str) -> Organization | None:
    """Resolve the organization a user's email belongs to.

    1. Normalize the domain (fail-closed on malformed).
    2. Match against *enabled* orgs' domains (exact, then longest subdomain).
    3. Fall back to the enabled public org.
    4. None => sign-in not permitted.
    """
    domain = normalize_domain(email)
    if domain is None:
        return None

    stmt = (
        select(
            OrganizationDomain.organization_id,
            OrganizationDomain.domain,
            OrganizationDomain.include_subdomains,
        )
        .join(Organization, Organization.id == OrganizationDomain.organization_id)
        .where(Organization.enabled.is_(True))
    )
    rows = [tuple(r) for r in (await db.execute(stmt)).all()]
    matched = match_org_id(domain, rows)
    if matched is not None:
        return await db.get(Organization, matched)

    pub_stmt = select(Organization).where(
        Organization.is_public.is_(True), Organization.enabled.is_(True)
    )
    return (await db.execute(pub_stmt)).scalar_one_or_none()


async def workspace_allows_org(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    organization_id: uuid.UUID | None,
) -> bool:
    """True if the workspace permits members from this org.

    No allowed-org rows => open to all orgs (legacy behavior). A restricted
    workspace denies users whose org is None or not in the allowed set.
    """
    stmt = select(WorkspaceAllowedOrganization.organization_id).where(
        WorkspaceAllowedOrganization.workspace_id == workspace_id
    )
    allowed = set((await db.execute(stmt)).scalars().all())
    if not allowed:
        return True
    return organization_id in allowed
