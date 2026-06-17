"""Single structured access-log event per request. Pure ASGI, sits outermost."""

import time

from starlette.requests import Request
from starlette.routing import Match

from src.logging_events import log_access
from src.middleware.rate_limit import get_client_ip

_SKIP_PATHS = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/.well-known/jwks.json",
}


def _route_template(scope) -> str:
    """Low-cardinality route template (e.g. /echo/{name}) via re-match against
    the app's routes; falls back to the raw path when nothing matches (404)."""
    path = scope.get("path", "")
    app = scope.get("app")
    if app is None:
        return path
    for route in getattr(app, "routes", []):
        try:
            match, _ = route.matches(scope)
        except Exception:
            continue
        if match == Match.FULL:
            return getattr(route, "path", path)
    return path


class AccessLogMiddleware:
    def __init__(self, app, skip_paths=None):
        self.app = app
        self.skip_paths = skip_paths or _SKIP_PATHS

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") in self.skip_paths:
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        state = {"status": 500, "bytes": 0}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                state["status"] = message["status"]
            elif message["type"] == "http.response.body":
                state["bytes"] += len(message.get("body", b"") or b"")
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            try:
                status = state["status"]
                level = (
                    "info" if status < 400 else "warning" if status < 500 else "error"
                )
                fields = {
                    "http.method": scope.get("method"),
                    "http.route": _route_template(scope),
                    "http.status": status,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                    "resp_bytes": state["bytes"],
                    "source_ip": get_client_ip(Request(scope)),
                }
                state_obj = scope.get("state")
                for k in ("actor", "workspace_id", "caller_service"):
                    v = (
                        state_obj.get(k)
                        if isinstance(state_obj, dict)
                        else getattr(state_obj, k, None)
                    )
                    if v is not None:
                        fields[k] = v
                log_access("http.access", level=level, **fields)
            except Exception:
                pass  # never let logging break the response
