"""Service layer for DB-based service app registration and key validation."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.service_app import ServiceApp
from src.services.token_service import get_redis

_CACHE_KEY = "svc:key_cache"
_CACHE_TTL = 300  # 5 minutes


def _generate_key() -> tuple[str, str, str]:
    """Generate a service API key.

    Returns (plaintext_key, sha256_hex, display_prefix).
    """
    raw = secrets.token_urlsafe(32)
    plaintext = f"sk_{raw}"
    sha = hashlib.sha256(plaintext.encode()).hexdigest()
    prefix = f"sk_{raw[:4]}****"
    return plaintext, sha, prefix


async def create_service_app(
    db: AsyncSession,
    name: str,
    service_name: str,
    created_by: uuid.UUID | None = None,
) -> tuple[ServiceApp, str]:
    """Create a new service app. Returns (app, plaintext_key)."""
    plaintext, sha, prefix = _generate_key()
    app = ServiceApp(
        id=uuid.uuid4(),
        name=name,
        service_name=service_name,
        key_hash=sha,
        key_prefix=prefix,
        created_by=created_by,
    )
    db.add(app)
    await db.flush()
    await _invalidate_cache()
    return app, plaintext


async def validate_key(
    raw_key: str, db: AsyncSession
) -> tuple[str, uuid.UUID] | None:
    """Validate a raw API key. Returns (service_name, app_id) or None."""
    sha = hashlib.sha256(raw_key.encode()).hexdigest()

    # Try cache first
    r = await get_redis()
    cached = await r.hget(_CACHE_KEY, sha)
    if cached:
        svc, app_id_str = cached.split(":", 1)
        # Update last_used_at in background (best-effort)
        await _touch_last_used(db, uuid.UUID(app_id_str))
        return svc, uuid.UUID(app_id_str)

    # Cache miss — rebuild cache from DB
    await _rebuild_cache(db)

    # Retry from cache
    cached = await r.hget(_CACHE_KEY, sha)
    if cached:
        svc, app_id_str = cached.split(":", 1)
        await _touch_last_used(db, uuid.UUID(app_id_str))
        return svc, uuid.UUID(app_id_str)

    return None


async def rotate_key(
    db: AsyncSession, app_id: uuid.UUID
) -> tuple[ServiceApp, str]:
    """Rotate the API key for a service app. Returns (app, new_plaintext_key)."""
    app = await db.get(ServiceApp, app_id)
    if not app:
        raise ValueError("Service app not found")
    plaintext, sha, prefix = _generate_key()
    app.key_hash = sha
    app.key_prefix = prefix
    await db.flush()
    await _invalidate_cache()
    return app, plaintext


async def list_service_apps(db: AsyncSession) -> list[ServiceApp]:
    result = await db.execute(
        select(ServiceApp).order_by(ServiceApp.created_at.desc())
    )
    return list(result.scalars().all())


async def get_service_app(db: AsyncSession, app_id: uuid.UUID) -> ServiceApp | None:
    return await db.get(ServiceApp, app_id)


async def update_service_app(
    db: AsyncSession,
    app_id: uuid.UUID,
    name: str | None = None,
    is_active: bool | None = None,
) -> ServiceApp:
    app = await db.get(ServiceApp, app_id)
    if not app:
        raise ValueError("Service app not found")
    if name is not None:
        app.name = name
    if is_active is not None:
        app.is_active = is_active
    await db.flush()
    await _invalidate_cache()
    return app


async def delete_service_app(db: AsyncSession, app_id: uuid.UUID) -> None:
    app = await db.get(ServiceApp, app_id)
    if not app:
        raise ValueError("Service app not found")
    await db.delete(app)
    await db.flush()
    await _invalidate_cache()


async def has_active_apps(db: AsyncSession) -> bool:
    result = await db.execute(
        select(ServiceApp.id).where(ServiceApp.is_active == True).limit(1)  # noqa: E712
    )
    return result.scalar_one_or_none() is not None


# ── Internal helpers ─────────────────────────────────────────────────


async def _rebuild_cache(db: AsyncSession) -> None:
    """Load all active apps into the Redis hash cache."""
    r = await get_redis()
    result = await db.execute(
        select(ServiceApp).where(ServiceApp.is_active == True)  # noqa: E712
    )
    apps = result.scalars().all()
    pipe = r.pipeline()
    pipe.delete(_CACHE_KEY)
    for app in apps:
        pipe.hset(_CACHE_KEY, app.key_hash, f"{app.service_name}:{app.id}")
    pipe.expire(_CACHE_KEY, _CACHE_TTL)
    await pipe.execute()


async def _invalidate_cache() -> None:
    r = await get_redis()
    await r.delete(_CACHE_KEY)


async def _touch_last_used(db: AsyncSession, app_id: uuid.UUID) -> None:
    """Update last_used_at timestamp (best-effort, no commit)."""
    app = await db.get(ServiceApp, app_id)
    if app:
        app.last_used_at = datetime.now(UTC)
