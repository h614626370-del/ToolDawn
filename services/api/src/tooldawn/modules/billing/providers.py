import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select

from tooldawn.modules.admin.repository import audit
from tooldawn.modules.billing.models import OrderRecord, ProviderRecord
from tooldawn.modules.billing.provider_config import CATALOG, validate_config


class ProviderRepository:
    def __init__(self, control):
        self.control = control
        self.sessions = control.sessions
        self.box = control.box

    def decode(self, row):
        return json.loads(self.box.decrypt(row.config))

    def view(self, row, config_locked=False):
        config = self.decode(row)
        fields = CATALOG[row.kind]["fields"]
        return dict(
            id=row.id,
            name=row.name,
            kind=row.kind,
            enabled=row.enabled,
            config_locked=config_locked,
            methods=row.methods,
            sort_order=row.sort_order,
            revision=row.revision,
            config={f["key"]: config.get(f["key"], "") for f in fields if not f["secret"]},
            secrets_set={f["key"]: bool(config.get(f["key"])) for f in fields if f["secret"]},
            webhook_url=(
                f"{config.get('public_origin', '')}/api/v1/billing/providers/{row.id}/webhook"
            ),
        )

    async def listing(self, public=False):
        async with self.sessions() as db:
            query = select(ProviderRecord).order_by(
                ProviderRecord.sort_order, ProviderRecord.created_at
            )
            if public:
                query = query.where(ProviderRecord.enabled.is_(True))
            rows = (await db.scalars(query)).all()
            if public:
                return [
                    dict(
                        id=row.id,
                        name=row.name,
                        kind=row.kind,
                        methods=row.methods,
                        currencies=CATALOG[row.kind]["currencies"],
                    )
                    for row in rows
                ]
            used = set(
                (
                    await db.scalars(
                        select(OrderRecord.provider_id)
                        .distinct()
                        .where(OrderRecord.provider_id.is_not(None))
                    )
                ).all()
            )
            return [self.view(row, row.id in used) for row in rows]

    async def get(self, identity):
        async with self.sessions() as db:
            row = await db.get(ProviderRecord, identity)
            if not row:
                raise HTTPException(404, "支付供应商不存在。")
            return row

    async def save(self, data, actor, identity=None):
        async with self.sessions.begin() as db:
            row = await db.get(ProviderRecord, identity, with_for_update=True) if identity else None
            if identity and not row:
                raise HTTPException(404, "支付供应商不存在。")
            if data.revision != (row.revision if row else 0):
                raise HTTPException(409, "记录已被其他操作更新，请刷新列表后重新编辑。")
            if row and row.kind != data.kind:
                raise HTTPException(422, "已有供应商不能更改类型。")
            spec = CATALOG[data.kind]
            if (
                row is None
                and (await db.scalar(select(func.count()).select_from(ProviderRecord))) >= 50
            ):
                raise HTTPException(422, "支付供应商数量已达上限。")
            if (
                not data.name.strip()
                or len(set(data.methods)) != len(data.methods)
                or not set(data.methods) <= set(spec["methods"])
            ):
                raise HTTPException(422, "支付方式或供应商名称不正确。")
            fields = {f["key"]: f for f in spec["fields"]}
            if set(data.config) - fields.keys():
                raise HTTPException(422, "支付供应商配置字段不正确。")
            old = self.decode(row) if row else {f["key"]: f["default"] for f in spec["fields"]}
            values = dict(old)
            for key, value in data.config.items():
                if value is not None:
                    values[key] = value.get_secret_value().strip()
            values = validate_config(data.kind, values, data.enabled)
            if (
                data.enabled
                and data.kind == "stripe"
                and self.control.base.environment != "production"
                and values["secret_key"].startswith("sk_live_")
            ):
                raise HTTPException(422, "非生产环境请使用 Stripe 测试密钥。")
            used = (
                await db.scalar(
                    select(func.count())
                    .select_from(OrderRecord)
                    .where(OrderRecord.provider_id == row.id)
                )
                if row
                else 0
            )
            if used and values != old:
                raise HTTPException(409, "该供应商已有订单，更换商户配置请新建供应商实例。")
            if row:
                row.name, row.enabled, row.methods = data.name.strip(), data.enabled, data.methods
                row.config = self.box.encrypt(json.dumps(values))
                row.sort_order, row.revision = data.sort_order, row.revision + 1
                row.updated_at = datetime.now(UTC)
            else:
                row = ProviderRecord(
                    id=uuid4(),
                    kind=data.kind,
                    name=data.name.strip(),
                    enabled=data.enabled,
                    methods=data.methods,
                    config=self.box.encrypt(json.dumps(values)),
                    sort_order=data.sort_order,
                    revision=1,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                db.add(row)
            audit(
                db,
                actor,
                "payment.provider.update" if identity else "payment.provider.create",
                str(row.id),
                ["name", "enabled", "methods", "sort_order", *data.config.keys()],
            )
            await db.flush()
            return self.view(row, bool(used))

    async def delete(self, identity, revision, actor):
        async with self.sessions.begin() as db:
            row = await db.get(ProviderRecord, identity, with_for_update=True)
            if not row:
                raise HTTPException(404, "支付供应商不存在。")
            if row.revision != revision:
                raise HTTPException(409, "记录已被其他操作更新，请刷新列表后重新编辑。")
            if await db.scalar(
                select(func.count())
                .select_from(OrderRecord)
                .where(OrderRecord.provider_id == identity)
            ):
                raise HTTPException(409, "已有订单的供应商不能删除，可以停用。")
            await db.delete(row)
            audit(db, actor, "payment.provider.delete", str(identity), ["provider"])
