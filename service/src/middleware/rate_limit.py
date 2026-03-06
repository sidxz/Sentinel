"""Rate limiting configuration using slowapi (Redis-backed) + global middleware."""

import redis.asyncio as aioredis
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.config import settings


def _proxy_aware_key_func(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For when behind a proxy."""
    if settings.behind_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


limiter = Limiter(
    key_func=_proxy_aware_key_func,
    storage_uri=settings.redis_url,
    storage_options=settings.redis_ssl_kwargs,
)


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests"},
        headers={"Retry-After": str(exc.retry_after)},
    )


_redis: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url, decode_responses=True, **settings.redis_ssl_kwargs
        )
    return _redis


# Lua script: atomic INCR + EXPIRE (avoids race where crash between
# INCR and EXPIRE leaves a key with no TTL forever).
_INCR_WITH_EXPIRE = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """IP-based rate limiter for all endpoints, backed by Redis.

    Applies a default 30 requests/minute per IP using a Redis sliding window.
    Endpoints with their own @limiter.limit() decorator have stricter limits
    and hit those first.
    """

    def __init__(self, app, requests_per_minute: int = 30):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.window = 60  # seconds

    async def dispatch(self, request: Request, call_next):
        # Skip health endpoint
        if request.url.path == "/health":
            return await call_next(request)

        ip = _proxy_aware_key_func(request)
        key = f"rl:global:{ip}"

        r = await _get_redis()
        count = await r.eval(_INCR_WITH_EXPIRE, 1, key, self.window)

        if count > self.rpm:
            ttl = await r.ttl(key)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": str(max(ttl, 1))},
            )

        return await call_next(request)
