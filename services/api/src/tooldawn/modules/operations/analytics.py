import asyncio
from datetime import UTC, datetime, timedelta
from time import perf_counter

from fastapi import HTTPException
from sqlalchemy import case, func, select, text

from tooldawn.modules.admin.models import AuditRecord
from tooldawn.modules.ai_tools.models import TextRunRecord
from tooldawn.modules.auth.models import SessionRecord, UserRecord
from tooldawn.modules.billing.models import OrderRecord
from tooldawn.modules.operations.models import ModelAccount, TicketRecord


class AnalyticsRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    async def usage(self, owner, q, status, slug, start, end, offset, limit):
        query = (
            select(TextRunRecord, UserRecord.email, ModelAccount.name)
            .join(
                UserRecord,
                UserRecord.id == TextRunRecord.user_id,
            )
            .outerjoin(ModelAccount, ModelAccount.id == TextRunRecord.account_id)
        )
        if owner:
            query = query.where(TextRunRecord.user_id == owner)
        elif q.strip():
            query = query.where(UserRecord.email.icontains(q.strip(), autoescape=True))
        if status:
            query = query.where(TextRunRecord.status == status)
        if slug:
            query = query.where(TextRunRecord.tool_slug == slug)
        if start:
            query = query.where(TextRunRecord.created_at >= start)
        if end:
            query = query.where(TextRunRecord.created_at < end)
        async with self.sessions() as db:
            total = await db.scalar(select(func.count()).select_from(query.subquery()))
            rows = await db.execute(
                query.order_by(
                    TextRunRecord.created_at.desc(),
                    TextRunRecord.id,
                )
                .offset(offset)
                .limit(limit)
            )
            return {
                "total": total,
                "items": [
                    {
                        **{
                            key: getattr(row, key)
                            for key in (
                                "id",
                                "tool_slug",
                                "status",
                                "cost",
                                "language",
                                "model",
                                "duration_ms",
                                "created_at",
                                "completed_at",
                                "error",
                            )
                        },
                        "email": email,
                        "account_name": name,
                        "charged": row.cost if row.status != "failed" else 0,
                    }
                    for row, email, name in rows
                ],
            }

    async def output(self, identity, owner):
        async with self.sessions() as db:
            row = await db.get(TextRunRecord, identity)
            if not row or row.user_id != owner:
                raise HTTPException(404, "生成记录不存在。")
            return {"id": row.id, "output": row.output, "status": row.status}

    async def dashboard(self, days):
        now = datetime.now(UTC)
        start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        async with self.sessions() as db:
            run_stats = (
                await db.execute(
                    select(
                        func.count(),
                        func.sum(case((TextRunRecord.status == "succeeded", 1), else_=0)),
                        func.sum(case((TextRunRecord.status == "failed", 1), else_=0)),
                        func.sum(case((TextRunRecord.status == "running", 1), else_=0)),
                        func.sum(
                            case((TextRunRecord.status == "succeeded", TextRunRecord.cost), else_=0)
                        ),
                        func.avg(TextRunRecord.duration_ms),
                    ).where(TextRunRecord.created_at >= start)
                )
            ).one()
            daily = await db.execute(
                select(
                    func.date_trunc("day", TextRunRecord.created_at).label("day"),
                    func.count(),
                    func.sum(case((TextRunRecord.status == "failed", 1), else_=0)),
                )
                .where(TextRunRecord.created_at >= start)
                .group_by("day")
                .order_by("day")
            )
            by_day = {day.date().isoformat(): (total, failed or 0) for day, total, failed in daily}
            revenue = await db.execute(
                select(
                    OrderRecord.currency,
                    func.sum(OrderRecord.unit_amount),
                )
                .where(OrderRecord.status == "paid", OrderRecord.paid_at >= start)
                .group_by(OrderRecord.currency)
            )
            return {
                "days": days,
                "users": await db.scalar(select(func.count()).select_from(UserRecord)),
                "new_users": await db.scalar(
                    select(func.count())
                    .select_from(UserRecord)
                    .where(
                        UserRecord.created_at >= start,
                    )
                ),
                "active_sessions": await db.scalar(
                    select(func.count())
                    .select_from(
                        SessionRecord,
                    )
                    .where(SessionRecord.expires_at > now)
                ),
                "open_tickets": await db.scalar(
                    select(func.count())
                    .select_from(
                        TicketRecord,
                    )
                    .where(TicketRecord.status.in_(["open", "processing"]))
                ),
                "runs": run_stats[0],
                "succeeded": run_stats[1] or 0,
                "failed": run_stats[2] or 0,
                "running": run_stats[3] or 0,
                "credits_used": run_stats[4] or 0,
                "average_ms": int(run_stats[5] or 0),
                "revenue": [
                    {"currency": currency, "amount": amount} for currency, amount in revenue
                ],
                "daily": [
                    {
                        "day": (start + timedelta(days=i)).date().isoformat(),
                        "total": by_day.get((start + timedelta(days=i)).date().isoformat(), (0, 0))[
                            0
                        ],
                        "failed": by_day.get(
                            (start + timedelta(days=i)).date().isoformat(), (0, 0)
                        )[1],
                    }
                    for i in range(days)
                ],
            }

    async def audit(self, q, offset, limit):
        query = select(AuditRecord, UserRecord.email).outerjoin(
            UserRecord,
            UserRecord.id == AuditRecord.actor_id,
        )
        if q.strip():
            query = query.where(AuditRecord.action.icontains(q.strip(), autoescape=True))
        async with self.sessions() as db:
            total = await db.scalar(select(func.count()).select_from(query.subquery()))
            rows = await db.execute(
                query.order_by(
                    AuditRecord.created_at.desc(),
                    AuditRecord.id,
                )
                .offset(offset)
                .limit(limit)
            )
            return {
                "total": total,
                "items": [
                    {
                        "id": row.id,
                        "email": email,
                        "action": row.action,
                        "target": row.target,
                        "changed_fields": row.changed_fields,
                        "created_at": row.created_at,
                    }
                    for row, email in rows
                ],
            }

    async def monitoring(self, state):
        async def probe(kind):
            started = perf_counter()
            try:
                async with asyncio.timeout(3):
                    if kind == "database":
                        async with self.sessions() as db:
                            await db.execute(text("SELECT 1"))
                    else:
                        if state.redis is None:
                            raise RuntimeError()
                        await state.redis.ping()
                return {"ok": True, "duration_ms": int((perf_counter() - started) * 1000)}
            except Exception:
                return {"ok": False, "duration_ms": int((perf_counter() - started) * 1000)}

        database = await probe("database")
        redis = await probe("redis")
        return {
            "database": database,
            "redis": redis,
            "uptime_seconds": int(perf_counter() - state.started_at),
            "checked_at": datetime.now(UTC),
            "http": state.metrics.snapshot(),
        }
