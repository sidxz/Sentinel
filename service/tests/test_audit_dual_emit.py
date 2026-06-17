import uuid

import pytest
from structlog.testing import capture_logs

from src.services import activity_service


class _FakeDB:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


@pytest.mark.asyncio
async def test_log_activity_writes_db_and_emits_event():
    db = _FakeDB()
    actor_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    target_id = uuid.uuid4()
    detail = {"name": "Acme"}
    with capture_logs() as logs:
        await activity_service.log_activity(
            db,
            action="workspace_created",
            target_type="workspace",
            target_id=target_id,
            actor_id=actor_id,
            workspace_id=workspace_id,
            detail=detail,
        )
    assert db.added  # DB row still created
    audit = [e for e in logs if e["event"] == "audit.activity"]
    assert audit
    assert audit[0]["category"] == "audit"
    assert audit[0]["action"] == "workspace_created"
    assert audit[0]["target_type"] == "workspace"
    assert audit[0]["detail"] == detail
    assert isinstance(audit[0]["actor"], str)
    assert isinstance(audit[0]["workspace_id"], str)


@pytest.mark.asyncio
async def test_log_activity_survives_emit_failure(monkeypatch):
    """Prove that log_activity succeeds even if log_audit raises."""

    def _boom(*a, **k):
        raise RuntimeError("structlog down")

    monkeypatch.setattr(activity_service, "log_audit", _boom)
    db = _FakeDB()
    entry = await activity_service.log_activity(
        db,
        action="x",
        target_type="t",
        target_id=uuid.uuid4(),
    )
    assert db.added  # DB row still created despite emit failure
    assert entry is not None
