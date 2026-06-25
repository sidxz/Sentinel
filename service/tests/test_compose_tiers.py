"""docker-compose.prod.yml runs two Sentinel listeners: a published public one and
an UNPUBLISHED internal one. This guards the deployment contract — the internal
service-key surface must never get a published port. PyYAML resolves the `<<` merge
key, so the merged `environment` (incl. the per-service TIER override) is asserted
on the loaded mapping without needing Docker."""

from pathlib import Path

import yaml

_COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.prod.yml"


def _services() -> dict:
    return yaml.safe_load(_COMPOSE.read_text())["services"]


def test_public_listener_is_published_with_tier_public():
    svc = _services()["sentinel"]
    assert svc["environment"]["TIER"] == "public"
    assert svc.get("ports"), "public listener must publish a port"


def test_internal_listener_exists_unpublished_with_tier_internal():
    services = _services()
    assert "sentinel-internal" in services, "internal listener service must exist"
    internal = services["sentinel-internal"]
    assert internal["environment"]["TIER"] == "internal"
    # The whole point of the split: the internal listener has NO socket on the host.
    assert not internal.get("ports"), "internal listener must NOT publish any port"


def test_internal_listener_waits_for_public_to_migrate():
    internal = _services()["sentinel-internal"]
    # public + all are the only migrator tiers; internal must start after public is
    # healthy so the schema exists before it serves authz/permissions.
    assert "sentinel" in internal.get("depends_on", {})
