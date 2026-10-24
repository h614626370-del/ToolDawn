from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from tooldawn.modules.admin.models import AuditRecord
from tooldawn.modules.admin.schemas import (
    AdminCategory,
    AdminTool,
    AdminToolPage,
    AdminUser,
    AdminUserPage,
    CategoryInput,
    ToolInput,
)
from tooldawn.modules.auth.models import EmailChallenge, SessionRecord, UserRecord
from tooldawn.modules.catalog.models import CategoryRecord, ToolRecord


def audit(db, actor: UUID, action: str, target: str, fields: list[str]):
    db.add(
        AuditRecord(
            id=uuid4(),
            actor_id=actor,
            action=action,
            target=target,
            changed_fields=fields,
            created_at=datetime.now(UTC),
        )
    )


class AdminRepository:
    def __init__(self, sessions: async_sessionmaker):
        self.sessions = sessions

    async def categories(self) -> list[AdminCategory]:
        async with self.sessions() as db:
            rows = (
                await db.execute(
                    select(CategoryRecord, func.count(ToolRecord.slug))
                    .outerjoin(ToolRecord, ToolRecord.category == CategoryRecord.slug)
                    .group_by(CategoryRecord.slug)
                    .order_by(CategoryRecord.sort_order, CategoryRecord.slug)
                )
            ).all()
            return [
                AdminCategory(
                    slug=item.slug,
                    name=item.name,
                    icon=item.icon,
                    color=item.color,
                    sort_order=item.sort_order,
                    revision=item.revision,
                    tool_count=count,
                )
                for item, count in rows
            ]

    async def tools(
        self,
        q: str,
        category: str | None,
        published: bool | None,
        offset: int,
        limit: int,
    ) -> AdminToolPage:
        query = select(ToolRecord)
        if q.strip():
            query = query.where(ToolRecord.name.icontains(q.strip(), autoescape=True))
        if category:
            query = query.where(ToolRecord.category == category)
        if published is not None:
            query = query.where(ToolRecord.published == published)
        async with self.sessions() as db:
            total = await db.scalar(select(func.count()).select_from(query.subquery()))
            records = (
                await db.scalars(
                    query.order_by(ToolRecord.sort_order, ToolRecord.slug)
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            return AdminToolPage(
                items=[AdminTool.model_validate(item, from_attributes=True) for item in records],
                total=total or 0,
            )

    async def save_category(self, data: CategoryInput, actor: UUID, create: bool):
        values = data.model_dump(exclude={"revision"})
        try:
            async with self.sessions.begin() as db:
                if create:
                    record = CategoryRecord(**values, revision=1)
                    db.add(record)
                else:
                    record = await db.scalar(
                        select(CategoryRecord)
                        .where(CategoryRecord.slug == data.slug)
                        .with_for_update()
                    )
                    self.check_revision(record, data.revision)
                    for key, value in values.items():
                        setattr(record, key, value)
                    record.revision += 1
                audit(
                    db,
                    actor,
                    "category.create" if create else "category.update",
                    data.slug,
                    list(values),
                )
                await db.flush()
                count = await db.scalar(
                    select(func.count())
                    .select_from(ToolRecord)
                    .where(
                        ToolRecord.category == data.slug,
                    )
                )
                return AdminCategory(**values, revision=record.revision, tool_count=count or 0)
        except IntegrityError:
            raise HTTPException(409, "分类标识已存在，请使用其他标识。") from None

    async def save_tool(self, data: ToolInput, actor: UUID, create: bool):
        values = data.model_dump(mode="json", exclude={"revision"})
        values["updated_at"] = datetime.now(UTC).date()
        try:
            async with self.sessions.begin() as db:
                if await db.get(CategoryRecord, data.category) is None:
                    raise HTTPException(422, "分类不存在，请刷新后重试。")
                if create:
                    record = ToolRecord(**values, revision=1)
                    db.add(record)
                else:
                    record = await db.scalar(
                        select(ToolRecord).where(ToolRecord.slug == data.slug).with_for_update()
                    )
                    self.check_revision(record, data.revision)
                    for key, value in values.items():
                        setattr(record, key, value)
                    record.revision += 1
                audit(
                    db, actor, "tool.create" if create else "tool.update", data.slug, list(values)
                )
                await db.flush()
                return AdminTool.model_validate(record, from_attributes=True)
        except IntegrityError:
            raise HTTPException(409, "工具标识已存在，请使用其他标识。") from None

    @staticmethod
    def check_revision(record, revision: int):
        if record is None:
            raise HTTPException(404, "记录不存在。")
        if record.revision != revision:
            raise HTTPException(409, "记录已被其他操作更新，请刷新列表后重新编辑。")

    async def users(self, q: str, offset: int, limit: int) -> AdminUserPage:
        query = select(UserRecord)
        if q.strip():
            query = query.where(UserRecord.email.icontains(q.strip(), autoescape=True))
        async with self.sessions() as db:
            total = await db.scalar(select(func.count()).select_from(query.subquery()))
            records = (
                await db.scalars(
                    query.order_by(UserRecord.created_at.desc(), UserRecord.id)
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            return AdminUserPage(
                items=[AdminUser.model_validate(item) for item in records],
                total=total or 0,
            )

    async def set_user_state(self, user_id: UUID, disabled: bool, actor: UUID) -> AdminUser:
        async with self.sessions.begin() as db:
            record = await db.scalar(
                select(UserRecord).where(UserRecord.id == user_id).with_for_update()
            )
            if record is None:
                raise HTTPException(404, "用户不存在。")
            if record.role == "admin" or record.id == actor:
                raise HTTPException(409, "管理员账户不能在此禁用，请通过服务器维护。")
            record.disabled = disabled
            if disabled:
                await db.execute(delete(SessionRecord).where(SessionRecord.user_id == user_id))
                await db.execute(
                    update(EmailChallenge)
                    .where(
                        EmailChallenge.email == record.email,
                    )
                    .values(consumed=True)
                )
            audit(
                db, actor, "user.disable" if disabled else "user.enable", str(user_id), ["disabled"]
            )
            return AdminUser.model_validate(record)
