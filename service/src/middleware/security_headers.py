from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds the configured maximum."""

    def __init__(self, app, max_bytes: int = 10_485_760):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_bytes:
            return JSONResponse(
                status_code=413, content={"detail": "Request body too large"}
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to every response."""

    def __init__(self, app, hsts: bool = False):
        super().__init__(app)
        self.hsts = hsts

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        _HTML_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; frame-ancestors 'none'"
        csp_override = response.headers.get("X-CSP-Override")
        if csp_override == "html-page":
            response.headers["Content-Security-Policy"] = _HTML_CSP
            del response.headers["X-CSP-Override"]
        else:
            if csp_override is not None:
                del response.headers["X-CSP-Override"]
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'"
            )
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Server"] = "daikon"
        if self.hsts:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response
