"""Rate limiting configuration using slowapi + global fallback middleware."""

import time
from collections import defaultdict

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

limiter = Limiter(key_func=get_remote_address)


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
        headers={"Retry-After": str(exc.retry_after)},
    )


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """Simple IP-based rate limiter for all endpoints without explicit limits.

    Applies a default 30 requests/minute per IP. Endpoints with their own
    @limiter.limit() decorator have stricter limits and hit those first.
    """

    def __init__(self, app, requests_per_minute: int = 30):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.window = 60  # seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        if request.client:
            return request.client.host
        return "unknown"

    async def dispatch(self, request: Request, call_next):
        # Skip health endpoint
        if request.url.path == "/health":
            return await call_next(request)

        ip = self._get_client_ip(request)
        now = time.time()
        cutoff = now - self.window

        # Prune old entries
        self._hits[ip] = [t for t in self._hits[ip] if t > cutoff]

        if len(self._hits[ip]) >= self.rpm:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(self.window)},
            )

        self._hits[ip].append(now)
        return await call_next(request)
