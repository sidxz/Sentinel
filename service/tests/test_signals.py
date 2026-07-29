"""Tier-1 security-signal tests: centroids, travel, first-seen, stuffing."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.config import settings
from src.services.country_centroids import CENTROIDS, centroid_km, haversine_km


class TestCentroids:
    def test_haversine_known_pair(self):
        # NYC ↔ London ≈ 5570 km
        nyc, london = (40.71, -74.0), (51.5, -0.13)
        assert haversine_km(nyc, london) == pytest.approx(5570, rel=0.02)

    def test_centroid_km_us_ru_is_far(self):
        km = centroid_km("US", "RU")
        assert km is not None and km > 6000

    def test_same_country_is_zero(self):
        assert centroid_km("DE", "DE") == 0

    def test_unknown_code_returns_none(self):
        assert centroid_km("US", "ZZ") is None
        assert centroid_km("ZZ", "US") is None

    def test_table_is_plausible(self):
        # Every entry is a valid lat/lon; majors are present.
        for cc, (lat, lon) in CENTROIDS.items():
            assert len(cc) == 2 and -90 <= lat <= 90 and -180 <= lon <= 180
        for major in ("US", "GB", "DE", "FR", "IN", "CN", "BR", "JP", "AU", "RU"):
            assert major in CENTROIDS


class FakeRedis:
    """Minimal async-redis stand-in: kv + sets, TTLs ignored."""

    def __init__(self):
        self.kv: dict = {}
        self.sets: dict[str, set] = {}

    async def get(self, k):
        return self.kv.get(k)

    async def set(self, k, v, ex=None, nx=False):
        if nx and k in self.kv:
            return None
        self.kv[k] = v
        return True

    async def sadd(self, k, m):
        s = self.sets.setdefault(k, set())
        if m in s:
            return 0
        s.add(m)
        return 1

    async def scard(self, k):
        return len(self.sets.get(k, set()))

    async def incr(self, k):
        self.kv[k] = int(self.kv.get(k, 0)) + 1
        return self.kv[k]

    async def expire(self, k, ttl):
        return True


NOW = 1_700_000_000.0
UID = uuid.uuid4()


def _patched(fake, geo):
    """Patch redis, geoip, and clock; return the log_activity patcher too."""
    from src.services import signal_service

    return (
        patch.object(signal_service, "get_redis", AsyncMock(return_value=fake)),
        patch.object(signal_service, "_lookup_country", lambda ip: geo),
        patch.object(signal_service, "_now", lambda: NOW),
        patch("src.services.activity_service.log_activity", new_callable=AsyncMock),
    )


@pytest.mark.asyncio
async def test_travel_signal_fires_on_fast_country_jump():
    from src.services import signal_service

    fake = FakeRedis()
    # Seen in the US one hour ago; now "in" Russia (≈7600 km) → ≈7600 km/h.
    fake.kv[f"geo:last:{UID}"] = json.dumps({"country": "US", "ts": NOW - 3600})
    p1, p2, p3, p4 = _patched(fake, ("RU", "Russia"))
    with p1, p2, p3, p4 as log_activity:
        await signal_service.on_login_success(
            AsyncMock(), user_id=UID, ip="203.0.113.9", user_agent="UA"
        )
    calls = [c.kwargs for c in log_activity.await_args_list]
    travel = [k for k in calls if k["action"] == "login_impossible_travel"]
    assert len(travel) == 1
    d = travel[0]["detail"]
    assert d["signal"] == "impossible_travel" and d["severity"] == "high"
    assert d["prev_country"] == "US" and d["country"] == "RU"
    assert d["kmh"] > settings.signal_impossible_travel_kmh
    assert travel[0]["target_id"] == UID and travel[0]["actor_id"] == UID


@pytest.mark.asyncio
async def test_travel_quiet_below_threshold_and_updates_baseline():
    from src.services import signal_service

    fake = FakeRedis()
    # US → GB over 24h ≈ 290 km/h — plausible.
    fake.kv[f"geo:last:{UID}"] = json.dumps({"country": "US", "ts": NOW - 86400})
    p1, p2, p3, p4 = _patched(fake, ("GB", "United Kingdom"))
    with p1, p2, p3, p4 as log_activity:
        await signal_service.on_login_success(
            AsyncMock(), user_id=UID, ip="203.0.113.9", user_agent="UA"
        )
    assert not [
        c
        for c in log_activity.await_args_list
        if c.kwargs["action"] == "login_impossible_travel"
    ]
    # Baseline moved to GB regardless.
    assert json.loads(fake.kv[f"geo:last:{UID}"])["country"] == "GB"


@pytest.mark.asyncio
async def test_travel_pair_flag_damps_pingpong():
    from src.services import signal_service

    fake = FakeRedis()
    p1, p2, p3, p4 = _patched(fake, ("RU", "Russia"))
    with p1, p2, p3, p4 as log_activity:
        for _ in range(2):
            fake.kv[f"geo:last:{UID}"] = json.dumps({"country": "US", "ts": NOW - 60})
            await signal_service.on_login_success(
                AsyncMock(), user_id=UID, ip="203.0.113.9", user_agent="UA"
            )
    travel = [
        c
        for c in log_activity.await_args_list
        if c.kwargs["action"] == "login_impossible_travel"
    ]
    assert len(travel) == 1  # second US↔RU flip inside the flag TTL is quiet


@pytest.mark.asyncio
async def test_first_sighting_seeds_silently():
    from src.services import signal_service

    fake = FakeRedis()
    p1, p2, p3, p4 = _patched(fake, ("US", "United States"))
    with p1, p2, p3, p4 as log_activity:
        await signal_service.on_login_success(
            AsyncMock(), user_id=UID, ip="203.0.113.9", user_agent="UA"
        )
    assert not [
        c
        for c in log_activity.await_args_list
        if c.kwargs["action"] == "login_impossible_travel"
    ]
    assert json.loads(fake.kv[f"geo:last:{UID}"])["country"] == "US"


@pytest.mark.asyncio
async def test_unresolvable_ip_is_quiet():
    from src.services import signal_service

    fake = FakeRedis()
    p1, p2, p3, p4 = _patched(fake, None)  # private/unresolvable
    with p1, p2, p3, p4 as log_activity:
        await signal_service.on_login_success(
            AsyncMock(), user_id=UID, ip="10.0.0.1", user_agent="UA"
        )
    assert not [
        c
        for c in log_activity.await_args_list
        if c.kwargs["action"] == "login_impossible_travel"
    ]


@pytest.mark.asyncio
async def test_fail_open_on_redis_error():
    from src.services import signal_service

    with (
        patch.object(signal_service, "get_redis", AsyncMock(side_effect=RuntimeError)),
        patch(
            "src.services.activity_service.log_activity", new_callable=AsyncMock
        ) as log_activity,
    ):
        # Must not raise.
        await signal_service.on_login_success(
            AsyncMock(), user_id=UID, ip="203.0.113.9", user_agent="UA"
        )
    log_activity.assert_not_awaited()


@pytest.mark.asyncio
async def test_disabled_flag_short_circuits(monkeypatch):
    from src.services import signal_service

    monkeypatch.setattr(settings, "signals_enabled", False)
    boom = AsyncMock(side_effect=AssertionError("redis must not be touched"))
    with patch.object(signal_service, "get_redis", boom):
        await signal_service.on_login_success(
            AsyncMock(), user_id=UID, ip="203.0.113.9", user_agent="UA"
        )


@pytest.mark.asyncio
async def test_travel_signal_emits_stream_event():
    from src.services import signal_service

    fake = FakeRedis()
    # Seen in the US one hour ago; now "in" Russia (≈7600 km) → ≈7600 km/h.
    fake.kv[f"geo:last:{UID}"] = json.dumps({"country": "US", "ts": NOW - 3600})
    p1, p2, p3, p4 = _patched(fake, ("RU", "Russia"))
    with (
        p1,
        p2,
        p3,
        p4,
        patch.object(signal_service, "log_security") as log_security_mock,
    ):
        await signal_service.on_login_success(
            AsyncMock(), user_id=UID, ip="203.0.113.9", user_agent="Mozilla/5.0"
        )
    # Verify stream event was emitted with correct parameters
    log_security_mock.assert_called_once()
    call_args = log_security_mock.call_args
    assert call_args[0][0] == "auth.signal.impossible_travel"
    assert call_args[1]["outcome"] == "anomaly"
    assert call_args[1]["severity"] == "high"
    assert call_args[1]["source_ip"] == "203.0.113.9"
    assert call_args[1]["actor"] == str(UID)
    assert "user_agent" not in call_args[1]  # Excluded from stream
