"""Sentinel.mint_m2m_token: mints, caches within TTL, re-mints after ~80%."""

import httpx
import pytest
import respx

from sentinel_auth import Sentinel
from sentinel_auth.types import SentinelError


def _sentinel() -> Sentinel:
    return Sentinel(
        base_url="https://sentinel.test",
        service_name="docs",
        service_key="svc-key",
        idp_public_key="x",
        idp_audience="a",
    )


@respx.mock
async def test_mints_then_serves_from_cache():
    route = respx.post("https://sentinel.test/realm/m2m-token").mock(
        return_value=httpx.Response(200, json={"token": "tok-1", "expires_in": 300})
    )
    s = _sentinel()
    assert await s.mint_m2m_token() == "tok-1"
    # Second call is within the 80%-TTL window: cached, no second HTTP call.
    assert await s.mint_m2m_token() == "tok-1"
    assert route.call_count == 1
    # X-Service-Key was sent.
    assert route.calls[0].request.headers["X-Service-Key"] == "svc-key"


@respx.mock
async def test_remints_after_refresh_window():
    respx.post("https://sentinel.test/realm/m2m-token").mock(
        return_value=httpx.Response(200, json={"token": "tok-1", "expires_in": 300})
    )
    s = _sentinel()
    await s.mint_m2m_token()
    # Force the refresh deadline into the past → next call re-mints.
    s._m2m_refresh_at = 0.0
    respx.post("https://sentinel.test/realm/m2m-token").mock(
        return_value=httpx.Response(200, json={"token": "tok-2", "expires_in": 300})
    )
    assert await s.mint_m2m_token() == "tok-2"


@respx.mock
async def test_mint_rejection_raises():
    respx.post("https://sentinel.test/realm/m2m-token").mock(
        return_value=httpx.Response(403, json={"detail": "not a realm member"})
    )
    s = _sentinel()
    with pytest.raises(SentinelError) as exc:
        await s.mint_m2m_token()
    assert exc.value.status_code == 403
