from datetime import UTC, datetime

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text

from tooldawn.config import Settings
from tooldawn.modules.admin.repository import audit
from tooldawn.modules.operations.models import ModelAccount, SettingRecord
from tooldawn.modules.operations.schemas import PaymentConfigInput, RuntimeConfig
from tooldawn.modules.operations.secrets import SecretBox

SECRET_FIELDS = {"smtp_password", "stripe_secret_key", "stripe_webhook_secret"}
ENV_FIELDS = {
    "mail_mode",
    "smtp_host",
    "smtp_port",
    "smtp_username",
    "smtp_from",
    "smtp_security",
    "credit_packages",
    "ai_tool_cost",
}


class SettingsRepository:
    def __init__(self, sessions, settings: Settings):
        self.sessions = sessions
        self.base = settings
        self.box = SecretBox(settings)

    async def read(self):
        async with self.sessions() as db:
            row = await db.get(SettingRecord, "runtime")
            return (dict(row.value), row.revision) if row else ({}, 0)

    def decode(self, stored):
        values = {key: getattr(self.base, key) for key in ENV_FIELDS}
        values.update(stored)
        for key in SECRET_FIELDS:
            if key in stored:
                values[key] = self.box.decrypt(stored[key]) if stored[key] else None
            else:
                value = getattr(self.base, key)
                values[key] = value.get_secret_value() if value else None
        return RuntimeConfig.model_validate(values)

    async def current(self) -> RuntimeConfig:
        stored, _ = await self.read()
        return self.decode(stored)

    async def effective(self) -> Settings:
        config = await self.current()
        data = self.base.model_dump()
        for key in ENV_FIELDS | SECRET_FIELDS:
            data[key] = getattr(config, key)
        return Settings(_env_file=None, **data)

    async def public(self):
        config = await self.current()
        return {
            key: getattr(config, key)
            for key in (
                "site_name",
                "site_logo",
                "announcement",
                "contact_email",
                "registration_enabled",
                "ai_enabled",
                "tickets_enabled",
            )
        }

    async def view(self):
        stored, revision = await self.read()
        config = self.decode(stored)
        data = config.model_dump(mode="json", exclude=SECRET_FIELDS)
        data.update({key + "_set": bool(getattr(config, key)) for key in SECRET_FIELDS})
        return {**data, "revision": revision}

    async def payment_view(self):
        view = await self.view()
        return {
            key: view[key]
            for key in (
                "revision",
                "credit_packages",
                "stripe_secret_key_set",
                "stripe_webhook_secret_set",
            )
        }

    async def save(self, data, actor):
        async with self.sessions.begin() as db:
            await db.execute(text("SELECT pg_advisory_xact_lock(72649103)"))
            row = await db.get(SettingRecord, "runtime", with_for_update=True)
            if (row.revision if row else 0) != data.revision:
                raise HTTPException(409, "记录已被其他操作更新，请刷新列表后重新编辑。")
            old = dict(row.value) if row else {}
            values = data.model_dump(mode="json", exclude=SECRET_FIELDS | {"revision"})
            changed_fields = list(values)
            payment_only = isinstance(data, PaymentConfigInput)
            if payment_only:
                values = {**old, **values}
            for key in SECRET_FIELDS:
                value = getattr(data, key, None)
                if value is not None:
                    changed_fields.append(key)
                    raw = value.get_secret_value()
                    if len(raw) > 1000:
                        raise HTTPException(422, "密钥长度不正确。")
                    values[key] = self.box.encrypt(raw) if raw else ""
                elif key in old:
                    values[key] = old[key]
            config = self.decode(values)
            refs = [config.default_account_id]
            refs += [item.account_id for item in config.tool_overrides.values()]
            for account_id in set(filter(None, refs)):
                if not await db.get(ModelAccount, account_id):
                    raise HTTPException(422, "模型账号不存在，请刷新后重试。")
            effective = self.base.model_dump()
            effective.update({key: getattr(config, key) for key in ENV_FIELDS | SECRET_FIELDS})
            try:
                Settings(_env_file=None, **effective)
            except ValidationError:
                raise HTTPException(422, "邮件或支付配置不完整，请检查配置。") from None
            if row:
                row.value, row.revision, row.updated_at = (
                    values,
                    row.revision + 1,
                    datetime.now(UTC),
                )
            else:
                db.add(
                    SettingRecord(
                        key="runtime", value=values, revision=1, updated_at=datetime.now(UTC)
                    )
                )
            audit(
                db,
                actor,
                "payments.update" if payment_only else "settings.update",
                "runtime",
                changed_fields,
            )
        return await self.payment_view() if payment_only else await self.view()


async def runtime(request):
    repo = getattr(request.app.state, "control", None)
    return (
        await repo.current()
        if repo
        else RuntimeConfig(ai_tool_cost=request.app.state.settings.ai_tool_cost)
    )


async def effective_settings(request):
    repo = getattr(request.app.state, "control", None)
    return await repo.effective() if repo else request.app.state.settings
