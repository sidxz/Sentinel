"""Refresh token rotation and access token revocation via Redis."""

import uuid
from datetime import UTC, datetime

import redis.asyncio as redis

from src.config import settings

_redis: redis.Redis | None = None

# Key prefixes
_REFRESH_PREFIX = "rt:"  # rt:{jti} → JSON {user_id, family_id}
_FAMILY_PREFIX = "rtf:"  # rtf:{family_id} → set of jtis
_BLACKLIST_PREFIX = "bl:"  # bl:{jti} → "1"
_CLIENT_APP_PREFIX = "cap:"  # cap:{client_app_id} → set of family_ids
_USER_FAMILIES_PREFIX = "uf:"  # uf:{user_id} → set of family_ids


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def store_refresh_token(
    jti: str,
    user_id: uuid.UUID,
    family_id: str,
    client_app_id: uuid.UUID | None = None,
) -> None:
    """Store a refresh token with its family for rotation tracking."""
    r = await get_redis()
    ttl = settings.refresh_token_expire_days * 86400
    pipe = r.pipeline()
    val = (
        f"{user_id}:{family_id}:{client_app_id}"
        if client_app_id
        else f"{user_id}:{family_id}"
    )
    pipe.set(f"{_REFRESH_PREFIX}{jti}", val, ex=ttl)
    pipe.sadd(f"{_FAMILY_PREFIX}{family_id}", jti)
    pipe.expire(f"{_FAMILY_PREFIX}{family_id}", ttl)
    pipe.sadd(f"{_USER_FAMILIES_PREFIX}{user_id}", family_id)
    pipe.expire(f"{_USER_FAMILIES_PREFIX}{user_id}", ttl)
    if client_app_id:
        pipe.sadd(f"{_CLIENT_APP_PREFIX}{client_app_id}", family_id)
        pipe.expire(f"{_CLIENT_APP_PREFIX}{client_app_id}", ttl)
    await pipe.execute()


async def consume_refresh_token(
    jti: str,
) -> tuple[uuid.UUID, str, uuid.UUID | None] | None:
    """Consume a refresh token (one-time use).

    Returns (user_id, family_id, client_app_id) if valid, None if already consumed/expired.
    """
    r = await get_redis()
    val = await r.getdel(f"{_REFRESH_PREFIX}{jti}")
    if not val:
        return None
    parts = val.split(":")
    user_id = uuid.UUID(parts[0])
    family_id = parts[1]
    client_app_id = uuid.UUID(parts[2]) if len(parts) > 2 else None
    return user_id, family_id, client_app_id


async def revoke_token_family(family_id: str) -> int:
    """Revoke all refresh tokens in a family (theft detection).

    Returns the number of tokens revoked.
    """
    r = await get_redis()
    jtis = await r.smembers(f"{_FAMILY_PREFIX}{family_id}")
    if not jtis:
        return 0
    pipe = r.pipeline()
    for jti in jtis:
        pipe.delete(f"{_REFRESH_PREFIX}{jti}")
    pipe.delete(f"{_FAMILY_PREFIX}{family_id}")
    results = await pipe.execute()
    return sum(1 for x in results[:-1] if x)


async def revoke_all_user_tokens(user_id: str) -> int:
    """Revoke all token families for a user. Returns total tokens revoked."""
    r = await get_redis()
    family_ids = await r.smembers(f"{_USER_FAMILIES_PREFIX}{user_id}")
    if not family_ids:
        return 0
    total = 0
    for fid in family_ids:
        total += await revoke_token_family(fid)
    await r.delete(f"{_USER_FAMILIES_PREFIX}{user_id}")
    return total


async def revoke_app_tokens(client_app_id: str) -> int:
    """Revoke all token families associated with a client app. Returns total tokens revoked."""
    r = await get_redis()
    family_ids = await r.smembers(f"{_CLIENT_APP_PREFIX}{client_app_id}")
    if not family_ids:
        return 0
    total = 0
    for fid in family_ids:
        total += await revoke_token_family(fid)
    await r.delete(f"{_CLIENT_APP_PREFIX}{client_app_id}")
    return total


async def blacklist_access_token(jti: str, exp: int) -> None:
    """Add an access token's jti to the denylist until it expires."""
    r = await get_redis()
    remaining = exp - int(datetime.now(UTC).timestamp())
    if remaining > 0:
        await r.set(f"{_BLACKLIST_PREFIX}{jti}", "1", ex=remaining)


async def is_access_token_blacklisted(jti: str) -> bool:
    """Check if an access token has been revoked."""
    r = await get_redis()
    return await r.exists(f"{_BLACKLIST_PREFIX}{jti}") > 0
