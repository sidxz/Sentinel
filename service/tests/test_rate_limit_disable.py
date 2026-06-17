"""Rate limiting must be disableable via config for the ephemeral pentest target.

The Layer-2 isolation prover provisions a matrix by driving many OAuth logins in a burst,
which trips the per-route limits (``5/minute`` admin, ``10/minute`` login). For a
throwaway, allowlisted target the limiter should be bypassable — without weakening the
production default (enabled). Fail-safe: the field defaults to True.
"""

import pytest

import src.middleware.rate_limit as rl
from src.config import settings


def _request(path: str = "/auth/login/dex"):
    from starlette.requests import Request

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "path": path,
            "headers": [],
            "query_string": b"",
            "client": ("10.0.0.9", 5555),
            "server": ("t", 80),
        }
    )


@pytest.mark.asyncio
async def test_global_rate_limit_bypassed_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", False)

    async def boom():
        raise AssertionError("rate limiter consulted its store despite being disabled")

    monkeypatch.setattr(rl, "_get_redis", boom)

    mw = rl.GlobalRateLimitMiddleware(app=None, requests_per_minute=1)

    async def call_next(request):
        return "passed-through"

    # Even past the configured limit, every call passes straight through.
    for _ in range(3):
        assert await mw.dispatch(_request(), call_next) == "passed-through"


@pytest.mark.asyncio
async def test_rate_limiting_enabled_by_default():
    # Production fail-safe: absent explicit opt-out, the limiter is on.
    assert settings.rate_limit_enabled is True
