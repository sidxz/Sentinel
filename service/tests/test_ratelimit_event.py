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
