"""RBAC action-usage insights: usage aggregates + role-mining anti-joins.

Reads the ``action_usage`` daily rollup (allowed checks) and ``action_denied``
activity events (denied checks). Role-mining sections cross-reference the
grant tables (user_roles + group_roles⋈group_memberships) to surface
granted-but-never-used pairs and roles nobody exercises.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.activity import ActivityLog
from src.models.role import ActionUsage
from src.models.user import User


def _day_iso(d) -> str:
    """date-or-string day → ISO string (func.date returns str on SQLite)."""
    return d.isoformat() if isinstance(d, date) else str(d)[:10]


async def actions_insights(
    db: AsyncSession, days: int = 30, workspace_id: uuid.UUID | None = None
) -> dict:
    now = datetime.now(UTC)
    since = (now - timedelta(days=days)).date()

    def scoped(stmt, col=ActionUsage.workspace_id):
        return stmt.where(col == workspace_id) if workspace_id else stmt

    total = func.sum(ActionUsage.count).label("count")

    top_actions = (
        await db.execute(
            scoped(
                select(ActionUsage.service_name, ActionUsage.action, total)
                .where(ActionUsage.day >= since)
                .group_by(ActionUsage.service_name, ActionUsage.action)
                .order_by(total.desc())
                .limit(20)
            )
        )
    ).all()

    by_service = (
        await db.execute(
            scoped(
                select(ActionUsage.service_name, total)
                .where(ActionUsage.day >= since)
                .group_by(ActionUsage.service_name)
                .order_by(total.desc())
            )
        )
    ).all()

    top_users = (
        await db.execute(
            scoped(
                select(ActionUsage.user_id, User.email, User.name, total)
                .join(User, User.id == ActionUsage.user_id)
                .where(ActionUsage.day >= since)
                .group_by(ActionUsage.user_id, User.email, User.name)
                .order_by(total.desc())
                .limit(20)
            )
        )
    ).all()

    allowed_rows = (
        await db.execute(
            scoped(
                select(ActionUsage.day, func.sum(ActionUsage.count))
                .where(ActionUsage.day >= since)
                .group_by(ActionUsage.day)
            )
        )
    ).all()
    denied_day = func.date(ActivityLog.created_at).label("day")
    denied_rows = (
        await db.execute(
            scoped(
                select(denied_day, func.count())
                .where(
                    ActivityLog.action == "action_denied",
                    ActivityLog.created_at >= now - timedelta(days=days),
                )
                .group_by(denied_day),
                col=ActivityLog.workspace_id,
            )
        )
    ).all()

    trend: dict[str, dict] = {}
    for d, n in allowed_rows:
        trend.setdefault(_day_iso(d), {"allowed": 0, "denied": 0})["allowed"] = n
    for d, n in denied_rows:
        trend.setdefault(_day_iso(d), {"allowed": 0, "denied": 0})["denied"] = n

    data_since = (
        await db.execute(select(func.min(ActionUsage.day)))
    ).scalar_one_or_none()

    return {
        "days": days,
        "since": since.isoformat(),
        "data_since": _day_iso(data_since) if data_since else None,
        "top_actions": [
            {"service_name": s, "action": a, "count": c} for s, a, c in top_actions
        ],
        "by_service": [{"service_name": s, "count": c} for s, c in by_service],
        "top_users": [
            {"user_id": str(u), "email": e, "name": n, "count": c}
            for u, e, n, c in top_users
        ],
        "trend": [{"day": d, **v} for d, v in sorted(trend.items())],
        # filled in by the role-mining pass (Task 2)
        "dormant_grants": {"total": 0, "items": []},
        "unused_roles": [],
    }
