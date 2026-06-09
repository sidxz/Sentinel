"""org_admin_service CRUD + guard logic, via fake sessions (no DB)."""

import uuid

import pytest

from src.services import org_admin_service as svc


class _Result:
    def __init__(self, *, scalar=None, scalars=None):
        self._scalar = scalar
        self._scalars = scalars or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalar_one(self):
        return self._scalar

    def scalars(self):
        parent = self

        class _S:
            def all(self_inner):
                return parent._scalars

        return _S()


class _FakeDB:
    """Serves queued execute() results; records added/deleted objects."""

    def __init__(self, *, execute_results=None, get_results=None):
        self._exec = list(execute_results or [])
        self._get = list(get_results or [])
        self.added = []
        self.deleted = []
        self.flushed = False

    async def execute(self, _stmt):
        return self._exec.pop(0)

    async def get(self, _model, _pk):
        return self._get.pop(0) if self._get else None

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        self.flushed = True


class _Org:
    def __init__(self, is_public=False):
        self.id = uuid.uuid4()
        self.name = "TAMU"
        self.slug = "tamu"
        self.is_public = is_public
        self.enabled = True


@pytest.mark.asyncio
async def test_create_organization_ok():
    db = _FakeDB(execute_results=[_Result(scalar=None)])  # slug not taken
    org = await svc.create_organization(db, name="TAMU", slug="tamu")
    assert org in db.added
    assert org.slug == "tamu"
    assert org.is_public is False
    assert db.flushed


@pytest.mark.asyncio
async def test_create_organization_duplicate_slug_conflicts():
    db = _FakeDB(execute_results=[_Result(scalar=uuid.uuid4())])  # slug taken
    with pytest.raises(svc.OrgConflict):
        await svc.create_organization(db, name="TAMU", slug="tamu")


@pytest.mark.asyncio
async def test_update_organization_not_found():
    db = _FakeDB(get_results=[None])
    with pytest.raises(svc.OrgNotFound):
        await svc.update_organization(db, uuid.uuid4(), name="New")


@pytest.mark.asyncio
async def test_update_organization_sets_fields():
    org = _Org()
    db = _FakeDB(get_results=[org])
    await svc.update_organization(db, org.id, name="Texas A&M", enabled=False)
    assert org.name == "Texas A&M"
    assert org.enabled is False


@pytest.mark.asyncio
async def test_delete_public_org_is_protected():
    pub = _Org(is_public=True)
    db = _FakeDB(get_results=[pub])
    with pytest.raises(svc.OrgProtected):
        await svc.delete_organization(db, pub.id)
    assert pub not in db.deleted


@pytest.mark.asyncio
async def test_delete_regular_org_ok():
    org = _Org()
    db = _FakeDB(get_results=[org])
    await svc.delete_organization(db, org.id)
    assert org in db.deleted
