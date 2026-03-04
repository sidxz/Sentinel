import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.activity import ActivityLog
from src.models.user import User


async def log_activity(
    db: AsyncSession,
    action: str,
    target_type: str,
    target_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID | None = None,
    detail: dict | None = None,
) -> ActivityLog:
    entry = ActivityLog(
        action=action,
        actor_id=actor_id,
        target_type=target_type,
        target_id=target_id,
        workspace_id=workspace_id,
        detail=detail,
    )
    db.add(entry)
    await db.flush()
    return entry


async def list_recent(db: AsyncSession, limit: int = 20) -> list[dict]:
    stmt = (
        select(ActivityLog, User.name.label("actor_name"), User.email.label("actor_email"))
        .outerjoin(User, ActivityLog.actor_id == User.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {
            "id": log.id,
            "action": log.action,
            "actor_id": log.actor_id,
            "actor_name": actor_name,
            "actor_email": actor_email,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "workspace_id": log.workspace_id,
            "detail": log.detail,
            "created_at": log.created_at,
        }
        for log, actor_name, actor_email in result.all()
    ]
