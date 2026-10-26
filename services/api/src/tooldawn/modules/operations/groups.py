from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import Field, field_validator
from sqlalchemy import delete, select

from tooldawn.modules.admin.repository import AdminRepository, audit
from tooldawn.modules.ai_tools.registry import TOOLS
from tooldawn.modules.catalog.models import ToolRecord
from tooldawn.modules.operations.models import ModelAccount, ModelGroup, ModelGroupMember
from tooldawn.modules.operations.schemas import StrictInput


class GroupInput(StrictInput):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    account_ids: list[UUID] = Field(default_factory=list, max_length=100)
    enabled: bool = True
    revision: int = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("分组名称不能为空")
        return value.strip()

    @field_validator("account_ids")
    @classmethod
    def unique(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("不能重复选择")
        return value


class GroupRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    async def listing(self, options=False):
        async with self.sessions() as db:
            groups = list(await db.scalars(select(ModelGroup).order_by(ModelGroup.created_at)))
            if options:
                return {
                    "items": [dict(id=g.id, name=g.name, enabled=g.enabled) for g in groups],
                    "text_tools": list(TOOLS),
                }
            members = list(
                (
                    await db.execute(select(ModelGroupMember).order_by(ModelGroupMember.priority))
                ).scalars()
            )
            tools = list(
                await db.scalars(select(ToolRecord).where(ToolRecord.model_group_id.is_not(None)))
            )
            items = [
                self.view(
                    g,
                    [m.account_id for m in members if m.group_id == g.id],
                    [t.slug for t in tools if t.model_group_id == g.id],
                )
                for g in groups
            ]
            return {"items": items, "total": len(items)}

    @staticmethod
    def view(row, account_ids, tool_slugs):
        return {
            key: getattr(row, key)
            for key in (
                "id",
                "name",
                "description",
                "enabled",
                "revision",
                "created_at",
                "updated_at",
            )
        } | {"account_ids": account_ids, "tool_slugs": tool_slugs}

    async def save(self, data, actor, identity=None):
        async with self.sessions.begin() as db:
            row = await db.get(ModelGroup, identity, with_for_update=True) if identity else None
            if identity:
                AdminRepository.check_revision(row, data.revision)
            tools = (
                list(
                    await db.scalars(
                        select(ToolRecord).where(ToolRecord.model_group_id == identity)
                    )
                )
                if identity
                else []
            )
            accounts = list(
                await db.scalars(
                    select(ModelAccount)
                    .where(ModelAccount.id.in_(data.account_ids))
                    .with_for_update()
                )
            )
            if len(accounts) != len(data.account_ids):
                raise HTTPException(422, "部分账号不存在，请刷新后重试。")
            if row is None:
                row = ModelGroup(id=uuid4(), created_at=datetime.now(UTC), revision=0)
                db.add(row)
            for key in ("name", "description", "enabled"):
                setattr(row, key, getattr(data, key))
            row.revision += 1
            row.updated_at = datetime.now(UTC)
            await db.flush()
            await db.execute(delete(ModelGroupMember).where(ModelGroupMember.group_id == row.id))
            for priority, account_id in enumerate(data.account_ids):
                db.add(ModelGroupMember(group_id=row.id, account_id=account_id, priority=priority))
            audit(
                db,
                actor,
                "model_group.update" if identity else "model_group.create",
                str(row.id),
                ["name", "description", "enabled", "account_ids"],
            )
            return self.view(row, data.account_ids, [t.slug for t in tools])

    async def remove(self, identity, revision, actor):
        async with self.sessions.begin() as db:
            row = await db.get(ModelGroup, identity, with_for_update=True)
            AdminRepository.check_revision(row, revision)
            if await db.scalar(
                select(ToolRecord.slug).where(ToolRecord.model_group_id == identity).limit(1)
            ):
                raise HTTPException(409, "请先解除工具绑定，再删除分组。")
            await db.delete(row)
            audit(db, actor, "model_group.delete", str(identity), [])
