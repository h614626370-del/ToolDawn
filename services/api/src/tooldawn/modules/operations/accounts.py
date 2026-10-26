import asyncio
import json
from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import uuid4

import httpx
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import select

from tooldawn.modules.admin.repository import AdminRepository, audit
from tooldawn.modules.operations.models import ModelAccount


def account_view(row):
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "name",
            "base_url",
            "model",
            "enabled",
            "revision",
            "created_at",
            "updated_at",
            "last_test_at",
            "last_test_ok",
            "last_test_ms",
            "capabilities",
            "capability_models",
            "cooldown_until",
            "last_failure_code",
        )
    } | {"key_set": bool(row.encrypted_key)}


class AccountRepository:
    def __init__(self, control):
        self.control = control
        self.sessions = control.sessions

    async def listing(self):
        async with self.sessions() as db:
            rows = list(await db.scalars(select(ModelAccount).order_by(ModelAccount.created_at)))
            return {"items": [account_view(row) for row in rows], "total": len(rows)}

    async def save(self, data, actor, identity=None):
        if self.control.base.environment == "production" and not data.base_url.startswith(
            "https://"
        ):
            raise HTTPException(422, "生产环境的模型地址必须使用 HTTPS。")
        async with self.sessions.begin() as db:
            row = await db.get(ModelAccount, identity, with_for_update=True) if identity else None
            if identity:
                AdminRepository.check_revision(row, data.revision)
            elif not data.api_key or not data.api_key.get_secret_value().strip():
                raise HTTPException(422, "新增模型账号需要 API Key。")
            if row is None:
                row = ModelAccount(
                    id=uuid4(),
                    created_at=datetime.now(UTC),
                    revision=0,
                )
                db.add(row)
            changed = row.base_url != data.base_url or row.model != data.model or bool(data.api_key)
            row.name, row.base_url, row.model, row.enabled = (
                data.name,
                data.base_url,
                data.model,
                data.enabled,
            )
            if data.api_key and data.api_key.get_secret_value().strip():
                key = data.api_key.get_secret_value().strip()
                if len(key) > 1000:
                    raise HTTPException(422, "密钥长度不正确。")
                row.encrypted_key = self.control.box.encrypt(key)
            changed = changed or row.capability_models != data.capability_models
            if changed:
                row.last_test_at = row.last_test_ok = row.last_test_ms = None
                row.cooldown_until = row.last_failure_at = row.last_failure_code = None
            row.capabilities = list(dict.fromkeys(data.capabilities))
            row.capability_models = data.capability_models
            row.revision += 1
            row.updated_at = datetime.now(UTC)
            audit(
                db,
                actor,
                "model_account.update" if identity else "model_account.create",
                str(row.id),
                [
                    "name",
                    "base_url",
                    "model",
                    "enabled",
                    "api_key",
                    "capabilities",
                    "capability_models",
                ],
            )
            await db.flush()
            return account_view(row)

    async def reset_health(self, identity, actor):
        async with self.sessions.begin() as db:
            row = await db.get(ModelAccount, identity, with_for_update=True)
            if not row:
                raise HTTPException(404, "模型账号不存在。")
            row.cooldown_until = row.last_failure_at = row.last_failure_code = None
            # Invalidate health updates from attempts started before this reset.
            row.revision += 1
            row.updated_at = datetime.now(UTC)
            audit(db, actor, "model_account.reset_health", str(identity), ["cooldown_until"])
            return account_view(row)

    async def mark_failure(self, identity, revision, failure):
        async with self.sessions.begin() as db:
            row = await db.get(ModelAccount, identity, with_for_update=True)
            if row and row.revision == revision:
                now = datetime.now(UTC)
                until = now + timedelta(seconds=failure.cooldown)
                row.cooldown_until = max(row.cooldown_until or until, until)
                row.last_failure_at = now
                row.last_failure_code = failure.code

    def settings_for(self, row, capability="text"):
        return self.control.base.model_copy(
            update={
                "llm_base_url": row.base_url,
                "llm_model": row.capability_models.get(capability, row.model),
                "llm_api_key": SecretStr(self.control.box.decrypt(row.encrypted_key)),
            }
        )

    async def group_plan(self, slug, required_capability=None):
        """None means legacy routing; an empty bound plan must fail closed."""
        from tooldawn.modules.catalog.models import ToolRecord
        from tooldawn.modules.operations.models import ModelGroup, ModelGroupMember

        async with self.sessions() as db:
            tool = await db.get(ToolRecord, slug)
            if not tool or not tool.model_group_id:
                return None
            group = await db.get(ModelGroup, tool.model_group_id)
            capability = required_capability or tool.model_capability or "text"
            ids = []
            if group and group.enabled:
                rows = await db.scalars(
                    select(ModelAccount)
                    .join(ModelGroupMember, ModelGroupMember.account_id == ModelAccount.id)
                    .where(ModelGroupMember.group_id == group.id)
                    .order_by(ModelGroupMember.priority)
                )
                ids = [row.id for row in rows if self.eligible(row, capability)]
            return tool.model_group_id, capability, ids

    @staticmethod
    def eligible(row, capability):
        return (
            row.enabled
            and capability in row.capabilities
            and (not row.cooldown_until or row.cooldown_until <= datetime.now(UTC))
        )

    async def group_candidate(self, group_id, capability, identity):
        from tooldawn.modules.operations.models import ModelGroup, ModelGroupMember

        async with self.sessions() as db:
            group = await db.get(ModelGroup, group_id)
            member = await db.get(ModelGroupMember, (group_id, identity))
            row = await db.get(ModelAccount, identity)
            if (
                not group
                or not group.enabled
                or not member
                or not row
                or not self.eligible(row, capability)
            ):
                return None
            return row.revision, self.settings_for(row, capability)

    async def resolve(self, slug, config=None):
        config = config or await self.control.current()
        override = config.tool_overrides.get(slug)
        account_id = (override.account_id if override else None) or config.default_account_id
        if account_id is None:
            return None, None
        async with self.sessions() as db:
            row = await db.get(ModelAccount, account_id)
            if not row or not self.eligible(row, "text"):
                return account_id, None
            return account_id, self.settings_for(row)

    async def test(self, identity, actor):
        async with self.sessions() as db:
            row = await db.get(ModelAccount, identity)
            if row is None:
                raise HTTPException(404, "模型账号不存在。")
            url, key, model, revision = (
                row.base_url,
                self.control.box.decrypt(row.encrypted_key),
                row.model,
                row.revision,
            )
        started = perf_counter()
        ok = False
        try:
            models = await self.fetch_models(url, key)
            ok = model in models and all(
                value in models for value in row.capability_models.values()
            )
        except HTTPException:
            ok = False
        duration = int((perf_counter() - started) * 1000)
        async with self.sessions.begin() as db:
            row = await db.get(ModelAccount, identity, with_for_update=True)
            if row and row.revision == revision:
                row.last_test_at, row.last_test_ok, row.last_test_ms = (
                    datetime.now(UTC),
                    ok,
                    duration,
                )
            audit(db, actor, "model_account.test", str(identity), ["last_test_ok"])
        return {
            "ok": ok,
            "duration_ms": duration,
            "message": "模型列表验证通过。" if ok else "未能验证模型，请检查地址、密钥和模型名称。",
        }

    @staticmethod
    async def fetch_models(url, key):
        try:
            async with asyncio.timeout(15):
                async with httpx.AsyncClient(
                    timeout=15, follow_redirects=False, trust_env=False
                ) as client:
                    async with client.stream(
                        "GET", url + "/models", headers={"Authorization": f"Bearer {key}"}
                    ) as response:
                        if response.status_code != 200:
                            raise ValueError()
                        content = bytearray()
                        async for chunk in response.aiter_bytes():
                            content.extend(chunk)
                            if len(content) > 524288:
                                raise ValueError()
                        items = json.loads(content)["data"]
                        if not isinstance(items, list):
                            raise ValueError()
                        models = sorted(
                            {
                                item["id"]
                                for item in items
                                if isinstance(item, dict)
                                and isinstance(item.get("id"), str)
                                and 0 < len(item["id"]) <= 120
                                and not any(ord(c) < 32 for c in item["id"])
                            }
                        )
                        return models[:1000]
        except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError):
            raise HTTPException(
                502, "无法获取模型列表，请检查服务地址和密钥，或手动填写模型名称。"
            ) from None

    async def discover(self, data, actor):
        if self.control.base.environment == "production" and not data.base_url.startswith(
            "https://"
        ):
            raise HTTPException(422, "生产环境的模型地址必须使用 HTTPS。")
        key = data.api_key.get_secret_value().strip() if data.api_key else ""
        async with self.sessions() as db:
            if data.account_id:
                row = await db.get(ModelAccount, data.account_id)
                AdminRepository.check_revision(row, data.revision)
                if not key:
                    key = self.control.box.decrypt(row.encrypted_key)
        if not key or len(key) > 1000:
            raise HTTPException(422, "请先填写 API Key。")
        models = await self.fetch_models(data.base_url, key)
        async with self.sessions.begin() as db:
            audit(
                db,
                actor,
                "model_account.discover_models",
                str(data.account_id) if data.account_id else "preview",
                [],
            )
        return {"items": models}
