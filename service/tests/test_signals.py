"""Tier-1 security-signal tests: centroids, travel, first-seen, stuffing."""

from __future__ import annotations

import pytest

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
