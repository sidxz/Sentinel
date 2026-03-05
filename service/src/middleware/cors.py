"""Dynamic CORS middleware — origins derived from active client apps."""

from urllib.parse import urlparse

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.client_app import ClientApp

logger = structlog.get_logger()

_ALLOWED_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
_ALLOWED_HEADERS = "Content-Type, Authorization, X-Service-Key"

_allowed_origins: set[str] = set()


def _extract_origin(uri: str) -> str | None:
    """Extract origin (scheme://host[:port]) from a URL."""
    parsed = urlparse(uri)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return None


async def refresh_origins(db: AsyncSession) -> None:
    """Rebuild allowed origins from active client apps + static config."""
    global _allowed_origins
    stmt = select(ClientApp.redirect_uris).where(ClientApp.is_active.is_(True))
    result = await db.execute(stmt)
    origins: set[str] = set(settings.cors_origin_list)
    for (uris,) in result.all():
        for uri in uris:
            origin = _extract_origin(uri)
            if origin:
                origins.add(origin)
    _allowed_origins = origins
    logger.info("cors_origins_refreshed", count=len(origins))


class DynamicCORSMiddleware:
    """ASGI middleware that checks Origin against a dynamic allow-list."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        origin = headers.get(b"origin", b"").decode()

        if not origin or origin not in _allowed_origins:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")

        # Preflight
        if method == "OPTIONS" and b"access-control-request-method" in headers:
            response_headers = [
                (b"access-control-allow-origin", origin.encode()),
                (b"access-control-allow-methods", _ALLOWED_METHODS.encode()),
                (b"access-control-allow-headers", _ALLOWED_HEADERS.encode()),
                (b"access-control-allow-credentials", b"true"),
                (b"access-control-max-age", b"600"),
                (b"vary", b"Origin"),
            ]
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": response_headers,
                }
            )
            await send({"type": "http.response.body", "body": b""})
            return

        # Normal request — inject CORS headers into response
        async def send_with_cors(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"access-control-allow-origin", origin.encode()))
                headers.append((b"access-control-allow-credentials", b"true"))
                headers.append((b"vary", b"Origin"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_cors)
