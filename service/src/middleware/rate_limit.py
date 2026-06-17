"""Rate limiting configuration using slowapi (Redis-backed) + global middleware."""

import time
from collections import defaultdict

import redis.asyncio as aioredis
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.config import settings

# Module-level fallback counter for when Redis is unavailable
_fallback_counts: dict[str, list[float]] = defaultdict(list)
_FALLBACK_WINDOW = 60  # seconds
_FALLBACK_LIMIT = 30  # requests per window
_fallback_request_count = 0


def get_client_ip(request: Request) -> str:
    """Extract the client IP, trusting only the configured proxy hop.

    When behind a reverse proxy, the real client IP is the ``trusted_proxy_count``-th
    entry from the RIGHT of ``X-Forwarded-For`` — the hop our trusted proxy
    appended. The leftmost entries are client-controlled and must never be
    trusted, otherwise an attacker can rotate them to evade per-IP rate limits.
    Falls back to the direct peer when the chain is shorter than expected.
    """
    if settings.behind_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            parts = [p.strip() for p in forwarded.split(",") if p.strip()]
            idx = settings.trusted_proxy_count
            if parts and 0 < idx <= len(parts):
                return parts[-idx]
    if request.client:
        return request.client.host
    return "unknown"


limiter = Limiter(
    key_func=get_client_ip,
    storage_uri=settings.redis_url,
    storage_options=settings.redis_ssl_kwargs,
    enabled=settings.rate_limit_enabled,  # disables every @limiter.limit() when off
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
        # Skip health checks, and bypass entirely when rate limiting is disabled
        # (ephemeral test/pentest targets — see settings.rate_limit_enabled).
        if request.url.path == "/health" or not settings.rate_limit_enabled:
            return await call_next(request)

        ip = get_client_ip(request)
        key = f"rl:global:{ip}"

        try:
            r = await _get_redis()
            count = await r.eval(_INCR_WITH_EXPIRE, 1, key, self.window)

            if count > self.rpm:
                ttl = await r.ttl(key)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests"},
                    headers={"Retry-After": str(max(ttl, 1))},
                )
        except Exception:
            # In-memory fallback when Redis is unavailable
            global _fallback_request_count
            now = time.time()
            key = ip
            _fallback_counts[key] = [
                t for t in _fallback_counts[key] if now - t < _FALLBACK_WINDOW
            ]
            if len(_fallback_counts[key]) >= _FALLBACK_LIMIT:
                return Response(status_code=429, content="Rate limit exceeded")
            _fallback_counts[key].append(now)

            # Periodic cleanup: prune empty keys every ~100 requests to prevent memory growth
            _fallback_request_count += 1
            if _fallback_request_count >= 100:
                _fallback_request_count = 0
                empty_keys = [k for k, v in _fallback_counts.items() if not v]
                for k in empty_keys:
                    del _fallback_counts[k]

        return await call_next(request)
