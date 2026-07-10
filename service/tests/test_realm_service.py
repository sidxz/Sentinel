"""Realm creation + membership (set/clear the service_apps.realm_id FK)."""

import uuid

import pytest

from src.models.service_app import ServiceApp


class _FakeDB:
    def __init__(self, get_result=None):
        self._get = get_result
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def get(self, _model, _pk):
        return self._get

    async def flush(self):
        pass


def _app() -> ServiceApp:
    return ServiceApp(
        id=uuid.uuid4(),
        name="Docs",
        service_name="docs",
        key_hash="x" * 64,
        key_prefix="sk_xxxx****",
        allowed_origins=[],
        allowed_idp_audiences=[],
    )


@pytest.mark.asyncio
async def test_create_realm_sets_fields():
    from src.services import realm_service

    realm = await realm_service.create_realm(
        _FakeDB(), name="Acme Suite", slug="acme-suite"
    )
    assert realm.slug == "acme-suite"
    assert realm.name == "Acme Suite"
    assert realm.m2m_ttl_s == 300


@pytest.mark.asyncio
async def test_add_member_sets_realm_id(monkeypatch):
    from src.services import realm_service

    app = _app()
    realm_id = uuid.uuid4()
    out = await realm_service.add_member(_FakeDB(get_result=app), realm_id, app.id)
    assert out.realm_id == realm_id


@pytest.mark.asyncio
async def test_remove_member_clears_realm_id(monkeypatch):
    from src.services import realm_service

    app = _app()
    app.realm_id = uuid.uuid4()
    out = await realm_service.remove_member(_FakeDB(get_result=app), app.id)
    assert out.realm_id is None


@pytest.mark.asyncio
async def test_add_member_missing_app_raises():
    from src.services import realm_service

    with pytest.raises(ValueError):
        await realm_service.add_member(
            _FakeDB(get_result=None), uuid.uuid4(), uuid.uuid4()
        )
