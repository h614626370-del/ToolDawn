from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select

from tooldawn.modules.admin.repository import AdminRepository, audit
from tooldawn.modules.auth.models import UserRecord
from tooldawn.modules.operations.models import TicketMessage, TicketRecord


def ticket_view(row, email):
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "user_id",
            "subject",
            "category",
            "status",
            "revision",
            "created_at",
            "updated_at",
        )
    } | {"email": email}


class TicketRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    async def listing(self, owner, status, q, offset, limit):
        query = select(TicketRecord, UserRecord.email).join(
            UserRecord, UserRecord.id == TicketRecord.user_id
        )
        if owner:
            query = query.where(TicketRecord.user_id == owner)
        if status:
            query = query.where(TicketRecord.status == status)
        if q.strip():
            query = query.where(TicketRecord.subject.icontains(q.strip(), autoescape=True))
        async with self.sessions() as db:
            total = await db.scalar(select(func.count()).select_from(query.subquery()))
            rows = await db.execute(
                query.order_by(
                    TicketRecord.updated_at.desc(),
                    TicketRecord.id,
                )
                .offset(offset)
                .limit(limit)
            )
            return {"items": [ticket_view(row, email) for row, email in rows], "total": total}

    async def get(self, identity, owner=None):
        async with self.sessions() as db:
            row = await self._owned(db, identity, owner)
            email = await db.scalar(select(UserRecord.email).where(UserRecord.id == row.user_id))
            messages = await db.execute(
                select(TicketMessage, UserRecord.display_name, UserRecord.email)
                .join(
                    UserRecord,
                    UserRecord.id == TicketMessage.author_id,
                )
                .where(TicketMessage.ticket_id == identity)
                .order_by(TicketMessage.created_at, TicketMessage.id)
                .limit(200)
            )
            return {
                **ticket_view(row, email),
                "messages": [
                    {
                        "id": msg.id,
                        "body": msg.body,
                        "staff": msg.staff,
                        "author": name or ("ToolDawn" if msg.staff else email),
                        "created_at": msg.created_at,
                    }
                    for msg, name, email in messages
                ],
            }

    @staticmethod
    async def _owned(db, identity, owner, lock=False):
        row = await db.get(TicketRecord, identity, with_for_update=lock)
        if row is None or (owner is not None and row.user_id != owner):
            raise HTTPException(404, "工单不存在。")
        return row

    async def create(self, data, actor):
        async with self.sessions.begin() as db:
            await db.get(UserRecord, actor, with_for_update=True)
            row = await db.get(TicketRecord, data.request_key)
            if row:
                first = await db.get(TicketMessage, data.request_key)
                if (
                    row.user_id != actor
                    or row.subject != data.subject
                    or row.category != data.category
                    or not first
                    or first.body != data.body
                ):
                    raise HTTPException(409, "重复请求的内容不一致。")
            else:
                now = datetime.now(UTC)
                row = TicketRecord(
                    id=data.request_key,
                    user_id=actor,
                    subject=data.subject,
                    category=data.category,
                    status="open",
                    revision=1,
                    created_at=now,
                    updated_at=now,
                )
                db.add(row)
                await db.flush()
                db.add(
                    TicketMessage(
                        id=data.request_key,
                        ticket_id=row.id,
                        author_id=actor,
                        staff=False,
                        body=data.body,
                        created_at=now,
                    )
                )
                audit(db, actor, "ticket.create", str(row.id), ["subject", "category"])
        return await self.get(data.request_key, actor)

    async def reply(self, identity, data, actor, staff=False):
        async with self.sessions.begin() as db:
            row = await self._owned(db, identity, None if staff else actor, lock=True)
            previous = await db.get(TicketMessage, data.request_key)
            if previous:
                if (
                    previous.ticket_id != identity
                    or previous.author_id != actor
                    or previous.body != data.body
                    or previous.staff != staff
                ):
                    raise HTTPException(409, "重复请求的内容不一致。")
            else:
                AdminRepository.check_revision(row, data.revision)
                if row.status == "closed":
                    raise HTTPException(409, "工单已关闭，请先重新打开。")
                count = await db.scalar(
                    select(func.count())
                    .select_from(TicketMessage)
                    .where(
                        TicketMessage.ticket_id == identity,
                    )
                )
                if count >= 200:
                    raise HTTPException(409, "工单消息已达上限，请新建工单。")
                if data.status and not staff:
                    raise HTTPException(403, "需要管理员权限。")
                now = datetime.now(UTC)
                db.add(
                    TicketMessage(
                        id=data.request_key,
                        ticket_id=identity,
                        author_id=actor,
                        staff=staff,
                        body=data.body,
                        created_at=now,
                    )
                )
                row.status = (data.status or "replied") if staff else "open"
                row.revision += 1
                row.updated_at = now
                audit(db, actor, "ticket.reply", str(identity), ["message", "status"])
        return await self.get(identity, None if staff else actor)

    async def state(self, identity, data, actor, staff=False):
        if not staff and data.status not in {"open", "closed"}:
            raise HTTPException(403, "需要管理员权限。")
        async with self.sessions.begin() as db:
            row = await self._owned(db, identity, None if staff else actor, lock=True)
            AdminRepository.check_revision(row, data.revision)
            row.status, row.updated_at = data.status, datetime.now(UTC)
            row.revision += 1
            audit(db, actor, "ticket.status", str(identity), ["status"])
        return await self.get(identity, None if staff else actor)
