import uuid
from datetime import datetime

from sqlalchemy import func, select
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


async def list_paginated(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    action: str | None = None,
    target_type: str | None = None,
    workspace_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> dict:
    base = (
        select(ActivityLog, User.name.label("actor_name"), User.email.label("actor_email"))
        .outerjoin(User, ActivityLog.actor_id == User.id)
    )
    count_q = select(func.count()).select_from(ActivityLog)

    if action:
        base = base.where(ActivityLog.action == action)
        count_q = count_q.where(ActivityLog.action == action)
    if target_type:
        base = base.where(ActivityLog.target_type == target_type)
        count_q = count_q.where(ActivityLog.target_type == target_type)
    if workspace_id:
        base = base.where(ActivityLog.workspace_id == workspace_id)
        count_q = count_q.where(ActivityLog.workspace_id == workspace_id)
    if actor_id:
        base = base.where(ActivityLog.actor_id == actor_id)
        count_q = count_q.where(ActivityLog.actor_id == actor_id)
    if from_date:
        base = base.where(ActivityLog.created_at >= from_date)
        count_q = count_q.where(ActivityLog.created_at >= from_date)
    if to_date:
        base = base.where(ActivityLog.created_at <= to_date)
        count_q = count_q.where(ActivityLog.created_at <= to_date)

    total = await db.scalar(count_q) or 0

    stmt = (
        base
        .order_by(ActivityLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    items = [
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
    return {"items": items, "total": total, "page": page, "page_size": page_size}


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
