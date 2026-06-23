import pytest
from starlette.requests import Request
from structlog.testing import capture_logs

import src.middleware.rate_limit as rl
from src.config import settings


def _request(path="/x", ip="10.0.0.9"):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "query_string": b"",
            "client": (ip, 5555),
            "server": ("t", 80),
        }
    )


@pytest.mark.asyncio
async def test_global_limit_emits_event_when_exceeded(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)

    class _R:
        async def eval(self, *a):
            return 999  # over the limit

        async def ttl(self, *a):
            return 30

    async def _get():
        return _R()

    monkeypatch.setattr(rl, "_get_redis", _get)
    mw = rl.GlobalRateLimitMiddleware(app=None, requests_per_minute=1)

    async def call_next(_req):
        raise AssertionError("must not pass through when over the limit")

    with capture_logs() as logs:
        resp = await mw.dispatch(_request(), call_next)

    assert resp.status_code == 429
    events = [e for e in logs if e["event"] == "ratelimit.exceeded"]
    assert events
    assert events[0]["outcome"] == "denied"
    assert events[0]["source_ip"] == "10.0.0.9"
    assert events[0]["http.route"] == "/x"
    assert len(events) == 1


@pytest.mark.asyncio
async def test_fallback_path_emits_global_ip_fallback(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)

    async def _get_failing():
        raise RuntimeError("Redis unavailable")

    monkeypatch.setattr(rl, "_get_redis", _get_failing)

    # Pre-fill the fallback counter so the limit is already reached
    import time

    rl._fallback_counts["10.0.0.9"] = [time.time()] * rl._FALLBACK_LIMIT

    mw = rl.GlobalRateLimitMiddleware(app=None, requests_per_minute=1)

    async def call_next(_req):
        raise AssertionError("must not pass through when over the fallback limit")

    try:
        with capture_logs() as logs:
            resp = await mw.dispatch(_request(ip="10.0.0.9"), call_next)
    finally:
        rl._fallback_counts.pop("10.0.0.9", None)

    assert resp.status_code == 429
    events = [e for e in logs if e["event"] == "ratelimit.exceeded"]
    assert len(events) == 1
    assert events[0]["reason"] == "global_ip_fallback"
    assert events[0]["source_ip"] == "10.0.0.9"


@pytest.mark.asyncio
async def test_slowapi_handler_emits_route_limit():
    from limits import parse
    from slowapi.errors import RateLimitExceeded
    from slowapi.wrappers import Limit

    lim = Limit(parse("5/minute"), lambda: "k", None, False, None, None, None, 1, True)
    exc = RateLimitExceeded(lim)

    with capture_logs() as logs:
        resp = await rl.rate_limit_exceeded_handler(_request(path="/admin/x"), exc)

    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) > 0
    events = [e for e in logs if e["event"] == "ratelimit.exceeded"]
    assert len(events) == 1
    assert events[0]["reason"] == "route_limit"
    assert events[0]["http.route"] == "/admin/x"
