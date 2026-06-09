"""invite_member must reject users whose org is not allowed by the workspace."""

import uuid

import pytest

from src.models.user import User
from src.services import workspace_service


class _ScalarResult:
    def __init__(self, value=None, scalars=None):
        self._value = value
        self._scalars = scalars or []

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        parent = self

        class _S:
            def all(self_inner):
                return parent._scalars

        return _S()


class _FakeSession:
    def __init__(self, exec_results):
        self._exec = list(exec_results)
        self.added = []
        self.committed = False

    async def execute(self, _stmt):
        return self._exec.pop(0)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


def _user_with_org(org_id):
    u = User(email="x@tamu.edu", name="X")
    u.id = uuid.uuid4()
    u.organization_id = org_id
    return u


@pytest.mark.asyncio
async def test_invite_rejected_when_org_not_allowed():
    user = _user_with_org(uuid.uuid4())
    allowed_org = uuid.uuid4()  # different from the user's org
    session = _FakeSession(
        exec_results=[
            _ScalarResult(value=user),  # select User by email
            _ScalarResult(scalars=[allowed_org]),  # workspace_allows_org query
        ]
    )
    with pytest.raises(ValueError, match="organization is not permitted"):
        await workspace_service.invite_member(
            session, uuid.uuid4(), "x@tamu.edu", role="viewer"
        )
    assert session.committed is False


@pytest.mark.asyncio
async def test_invite_allowed_when_workspace_open():
    org_id = uuid.uuid4()
    user = _user_with_org(org_id)
    session = _FakeSession(
        exec_results=[
            _ScalarResult(value=user),  # select User by email
            _ScalarResult(scalars=[]),  # no allowed-org rows => open
        ]
    )
    membership = await workspace_service.invite_member(
        session, uuid.uuid4(), "x@tamu.edu", role="viewer"
    )
    assert membership.user_id == user.id
    assert session.committed is True
