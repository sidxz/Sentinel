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
    with capture_logs() as logs:
        await activity_service.log_activity(
            db,
            action="workspace_created",
            target_type="workspace",
            target_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            detail={"name": "Acme"},
        )
    assert db.added  # DB row still created
    audit = [e for e in logs if e["event"] == "audit.activity"]
    assert audit
    assert audit[0]["category"] == "audit"
    assert audit[0]["action"] == "workspace_created"
    assert audit[0]["target_type"] == "workspace"
