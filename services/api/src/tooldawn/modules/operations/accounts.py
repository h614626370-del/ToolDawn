import json
from datetime import UTC, datetime
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
            if changed:
                row.last_test_at = row.last_test_ok = row.last_test_ms = None
            row.revision += 1
            row.updated_at = datetime.now(UTC)
            audit(
                db,
                actor,
                "model_account.update" if identity else "model_account.create",
                str(row.id),
                ["name", "base_url", "model", "enabled", "api_key"],
            )
            await db.flush()
            return account_view(row)

    async def resolve(self, slug, config=None):
        config = config or await self.control.current()
        override = config.tool_overrides.get(slug)
        account_id = (override.account_id if override else None) or config.default_account_id
        if account_id is None:
            return None, None
        async with self.sessions() as db:
            row = await db.get(ModelAccount, account_id)
            if not row or not row.enabled:
                return account_id, None
            settings = self.control.base.model_copy(
                update={
                    "llm_base_url": row.base_url,
                    "llm_model": row.model,
                    "llm_api_key": SecretStr(self.control.box.decrypt(row.encrypted_key)),
                }
            )
            return account_id, settings

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
            async with httpx.AsyncClient(
                timeout=15, follow_redirects=False, trust_env=False
            ) as client:
                async with client.stream(
                    "GET", url + "/models", headers={"Authorization": f"Bearer {key}"}
                ) as response:
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 262144:
                            break
                    if response.status_code == 200 and len(content) <= 262144:
                        payload = json.loads(content)
                        ok = any(item.get("id") == model for item in payload.get("data", []))
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
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
