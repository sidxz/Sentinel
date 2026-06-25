# service/src/services/realm_service.py
"""Service layer for realms (trusted app groups) + membership."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.realm import Realm
from src.models.service_app import ServiceApp


async def create_realm(
    db: AsyncSession,
    *,
    name: str,
    slug: str,
    m2m_ttl_s: int = 300,
    created_by: uuid.UUID | None = None,
) -> Realm:
    realm = Realm(
        id=uuid.uuid4(),
        name=name,
        slug=slug,
        m2m_ttl_s=m2m_ttl_s,
        created_by=created_by,
    )
    db.add(realm)
    await db.flush()
    return realm


async def get_realm(db: AsyncSession, realm_id: uuid.UUID) -> Realm | None:
    return await db.get(Realm, realm_id)


async def get_realm_by_slug(db: AsyncSession, slug: str) -> Realm | None:
    """Resolve a realm by its shared-scope slug. Used by /realm/whoami (for the
    display name) and /realm/m2m-token (for is_active + m2m_ttl_s)."""
    result = await db.execute(select(Realm).where(Realm.slug == slug))
    return result.scalar_one_or_none()


async def list_realms(db: AsyncSession) -> list[Realm]:
    result = await db.execute(select(Realm).order_by(Realm.created_at.desc()))
    return list(result.scalars().all())


async def add_member(
    db: AsyncSession, realm_id: uuid.UUID, service_app_id: uuid.UUID
) -> ServiceApp:
    """Assign a service app to a realm. The single FK enforces one-realm-max:
    re-assigning simply overwrites the prior realm. Invalidates the service-key
    cache because it stores the member's realm slug."""
    from src.services import service_app_service

    app = await db.get(ServiceApp, service_app_id)
    if not app:
        raise ValueError("Service app not found")
    app.realm_id = realm_id
    await db.flush()
    await service_app_service._invalidate_cache()
    return app


async def remove_member(db: AsyncSession, service_app_id: uuid.UUID) -> ServiceApp:
    from src.services import service_app_service

    app = await db.get(ServiceApp, service_app_id)
    if not app:
        raise ValueError("Service app not found")
    app.realm_id = None
    await db.flush()
    await service_app_service._invalidate_cache()
    return app
