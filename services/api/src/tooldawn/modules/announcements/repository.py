from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert

from tooldawn.modules.admin.repository import audit
from tooldawn.modules.announcements.models import Announcement, AnnouncementRead
from tooldawn.modules.announcements.schemas import (
    AdminAnnouncement,
    AnnouncementView,
    PublicAnnouncement,
)


def visible(user_id, now):
    return and_(
        Announcement.status == "active",
        or_(Announcement.starts_at.is_(None), Announcement.starts_at <= now),
        or_(Announcement.ends_at.is_(None), Announcement.ends_at > now),
        Announcement.audience.in_(["all", "members"] if user_id else ["all"]),
    )


def public_view(row, read_at):
    return PublicAnnouncement(**AnnouncementView.model_validate(row).model_dump(), read_at=read_at)


class AnnouncementRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    async def listing(self, user_id, offset, limit):
        query = (
            select(Announcement, AnnouncementRead.read_at)
            .outerjoin(
                AnnouncementRead,
                and_(
                    AnnouncementRead.announcement_id == Announcement.id,
                    AnnouncementRead.user_id == user_id,
                    AnnouncementRead.revision == Announcement.revision,
                ),
            )
            .where(visible(user_id, datetime.now(UTC)))
        )
        order = (Announcement.created_at.desc(), Announcement.id)
        async with self.sessions() as db:
            total = await db.scalar(select(func.count()).select_from(query.subquery()))
            unread = query.where(AnnouncementRead.read_at.is_(None))
            count = await db.scalar(select(func.count()).select_from(unread.subquery()))
            guest_versions = {}
            if user_id is None:
                versions = await db.execute(
                    select(Announcement.id, Announcement.revision).where(
                        visible(None, datetime.now(UTC))
                    )
                )
                guest_versions = {str(identity): revision for identity, revision in versions}
            rows = await db.execute(query.order_by(*order).offset(offset).limit(limit))
            popups = await db.execute(
                unread.where(Announcement.notify_mode == "popup").order_by(*order).limit(10)
            )
            return {
                "items": [public_view(row, read_at) for row, read_at in rows],
                "total": total,
                "unread_count": count,
                "popups": [public_view(row, read_at) for row, read_at in popups],
                "guest_versions": guest_versions,
            }

    async def admin_listing(self, status, q, offset, limit):
        query = select(Announcement)
        if status:
            query = query.where(Announcement.status == status)
        if q.strip():
            query = query.where(Announcement.title.icontains(q.strip(), autoescape=True))
        count = (
            select(func.count())
            .where(
                AnnouncementRead.announcement_id == Announcement.id,
                AnnouncementRead.revision == Announcement.revision,
            )
            .correlate(Announcement)
            .scalar_subquery()
        )
        async with self.sessions() as db:
            total = await db.scalar(select(func.count()).select_from(query.subquery()))
            rows = await db.execute(
                query.add_columns(count)
                .order_by(Announcement.created_at.desc(), Announcement.id)
                .offset(offset)
                .limit(limit)
            )
            return {
                "total": total,
                "items": [
                    AdminAnnouncement(
                        **AnnouncementView.model_validate(row).model_dump(),
                        read_count=count,
                    )
                    for row, count in rows
                ],
            }

    async def save(self, identity, data, actor):
        async with self.sessions.begin() as db:
            now = datetime.now(UTC)
            fields = data.model_dump(exclude={"revision"})
            if identity:
                row = await db.get(Announcement, identity, with_for_update=True)
                if not row:
                    raise HTTPException(404, "公告不存在。")
                if row.revision != data.revision:
                    raise HTTPException(409, "公告已被修改，请刷新后重试。")
                changed = [key for key, value in fields.items() if getattr(row, key) != value]
                if changed:
                    for key, value in fields.items():
                        setattr(row, key, value)
                    row.revision += 1
                    row.updated_at = now
                    audit(db, actor, "announcement.update", str(row.id), changed)
            else:
                row = Announcement(
                    id=uuid4(),
                    **fields,
                    revision=1,
                    created_by=actor,
                    created_at=now,
                    updated_at=now,
                )
                db.add(row)
                audit(db, actor, "announcement.create", str(row.id), list(fields))
            await db.flush()
            return AnnouncementView.model_validate(row)

    async def mark_read(self, data, user_id):
        async with self.sessions.begin() as db:
            # Lock announcements in a stable order; updates cannot race the read revision.
            ids = sorted({item.id for item in data.items})
            rows = (
                await db.scalars(
                    select(Announcement)
                    .where(Announcement.id.in_(ids), visible(user_id, datetime.now(UTC)))
                    .order_by(Announcement.id)
                    .with_for_update()
                )
            ).all()
            expected = {item.id: item.revision for item in data.items}
            if len(rows) != len(ids):
                raise HTTPException(404, "公告不存在或已结束展示。")
            if any(row.revision != expected[row.id] for row in rows):
                raise HTTPException(409, "公告已更新，请重新打开后阅读。")
            for row in rows:
                statement = insert(AnnouncementRead).values(
                    announcement_id=row.id,
                    user_id=user_id,
                    revision=row.revision,
                    read_at=datetime.now(UTC),
                )
                await db.execute(
                    statement.on_conflict_do_update(
                        index_elements=["announcement_id", "user_id"],
                        set_={
                            "revision": statement.excluded.revision,
                            "read_at": statement.excluded.read_at,
                        },
                        where=AnnouncementRead.revision != row.revision,
                    )
                )
