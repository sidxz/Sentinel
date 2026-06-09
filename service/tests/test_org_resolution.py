"""resolve_organization + workspace_allows_org, exercised with fake sessions."""

import uuid

import pytest

from src.services import organization_service as org_svc


class _DomainRow(tuple):
    """Stand-in for a (org_id, domain, include_subdomains) result row."""


class _ExecResult:
    def __init__(self, *, rows=None, scalar=None, scalars=None):
        self._rows = rows or []
        self._scalar = scalar
        self._scalars = scalars or []

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        parent = self

        class _S:
            def all(self_inner):
                return parent._scalars

        return _S()


class _FakeSession:
    """Serves queued _ExecResult objects for successive execute() calls and a
    dict for get()."""

    def __init__(self, exec_results, get_map=None):
        self._exec = list(exec_results)
        self._get = get_map or {}

    async def execute(self, _stmt):
        return self._exec.pop(0)

    async def get(self, _model, pk):
        return self._get.get(pk)


@pytest.mark.asyncio
async def test_resolve_matched_org_returned():
    org_id = uuid.uuid4()
    org = object()
    session = _FakeSession(
        exec_results=[_ExecResult(rows=[(org_id, "tamu.edu", False)])],
        get_map={org_id: org},
    )
    result = await org_svc.resolve_organization(session, "alice@tamu.edu")
    assert result is org


@pytest.mark.asyncio
async def test_resolve_falls_back_to_public():
    public = object()
    session = _FakeSession(
        exec_results=[
            _ExecResult(rows=[]),          # no domain match
            _ExecResult(scalar=public),    # enabled public org
        ]
    )
    result = await org_svc.resolve_organization(session, "someone@gmail.com")
    assert result is public


@pytest.mark.asyncio
async def test_resolve_none_when_no_match_and_no_public():
    session = _FakeSession(
        exec_results=[_ExecResult(rows=[]), _ExecResult(scalar=None)]
    )
    result = await org_svc.resolve_organization(session, "someone@gmail.com")
    assert result is None


@pytest.mark.asyncio
async def test_resolve_malformed_email_short_circuits_to_none():
    # No execute() results queued: a malformed domain must not hit the DB.
    session = _FakeSession(exec_results=[])
    result = await org_svc.resolve_organization(session, "not-an-email")
    assert result is None


@pytest.mark.asyncio
async def test_workspace_open_when_no_rows():
    session = _FakeSession(exec_results=[_ExecResult(scalars=[])])
    assert await org_svc.workspace_allows_org(session, uuid.uuid4(), uuid.uuid4()) is True


@pytest.mark.asyncio
async def test_workspace_restricts_to_allowed_set():
    allowed = uuid.uuid4()
    other = uuid.uuid4()
    session = _FakeSession(exec_results=[_ExecResult(scalars=[allowed])])
    assert await org_svc.workspace_allows_org(session, uuid.uuid4(), allowed) is True

    session = _FakeSession(exec_results=[_ExecResult(scalars=[allowed])])
    assert await org_svc.workspace_allows_org(session, uuid.uuid4(), other) is False


@pytest.mark.asyncio
async def test_workspace_denies_orgless_user_when_restricted():
    allowed = uuid.uuid4()
    session = _FakeSession(exec_results=[_ExecResult(scalars=[allowed])])
    assert await org_svc.workspace_allows_org(session, uuid.uuid4(), None) is False
