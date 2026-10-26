from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select

from tooldawn.modules.ai_tools.models import TextRunRecord
from tooldawn.modules.ai_tools.schemas import Run, RunInput
from tooldawn.modules.billing.repository import BillingRepository

FAILED = "生成未完成，已退回本次积分，请重新尝试。"


class TextRunRepository:
    def __init__(self, billing: BillingRepository):
        self.billing = billing
        self.sessions = billing.sessions

    async def _expire(self, db, user_id: UUID):
        records = await db.scalars(
            select(TextRunRecord).where(
                TextRunRecord.user_id == user_id,
                TextRunRecord.status == "running",
                TextRunRecord.expires_at < datetime.now(UTC),
            )
        )
        for run in records:
            await self._fail(db, run)

    async def _fail(self, db, run: TextRunRecord):
        if run.status != "running":
            return
        if run.cost:
            await self.billing._apply(
                db, run.user_id, run.cost, "tool_refund", f"refund:{run.id}", run.tool_slug
            )
        run.status, run.error = "failed", FAILED
        self._complete(run)

    @staticmethod
    def _complete(run):
        run.completed_at = datetime.now(UTC)
        run.duration_ms = max(0, int((run.completed_at - run.created_at).total_seconds() * 1000))

    async def prepare(
        self,
        user_id: UUID,
        slug: str,
        data: RunInput,
        fingerprint: str,
        cost: int,
        account_id: UUID | None = None,
        model: str | None = None,
    ) -> tuple[Run, bool]:
        async with self.sessions.begin() as db:
            owner = await self.billing._lock_user(db, user_id)
            if owner.disabled:
                raise HTTPException(403, "账户已禁用。")
            await self._expire(db, user_id)
            previous = await db.scalar(
                select(TextRunRecord).where(
                    TextRunRecord.user_id == user_id,
                    TextRunRecord.request_key == data.request_key,
                )
            )
            if previous:
                if previous.fingerprint != fingerprint:
                    raise HTTPException(409, "重复请求的内容不一致。")
                return Run.model_validate(previous), False
            active = await db.scalar(
                select(TextRunRecord.id)
                .where(TextRunRecord.user_id == user_id, TextRunRecord.status == "running")
                .limit(1)
            )
            if active:
                raise HTTPException(409, "你还有一个任务正在生成，请稍后再试。")
            now = datetime.now(UTC)
            run = TextRunRecord(
                id=uuid4(),
                user_id=user_id,
                request_key=data.request_key,
                fingerprint=fingerprint,
                tool_slug=slug,
                status="running",
                cost=cost,
                language=data.language,
                created_at=now,
                expires_at=now + timedelta(seconds=120),
                account_id=account_id,
                model=model,
            )
            if cost:
                await self.billing._apply(db, user_id, -cost, "tool_usage", f"tool:{run.id}", slug)
            db.add(run)
            await db.flush()
            return Run.model_validate(run), True

    async def finish(self, user_id: UUID, run_id: UUID, output: str | None) -> Run:
        async with self.sessions.begin() as db:
            await self.billing._lock_user(db, user_id)
            run = await db.get(TextRunRecord, run_id)
            if run is None or run.user_id != user_id:
                raise HTTPException(404, "生成记录不存在。")
            if run.status == "running":
                if output and run.expires_at > datetime.now(UTC):
                    run.status, run.output = "succeeded", output
                    self._complete(run)
                else:
                    await self._fail(db, run)
            return Run.model_validate(run)

    async def record_attempt(self, user_id, run_id, group_id, account_id, model, code):
        async with self.sessions.begin() as db:
            await self.billing._lock_user(db, user_id)
            run = await db.get(TextRunRecord, run_id)
            if not run or run.user_id != user_id or run.status != "running":
                return
            run.group_id, run.account_id, run.model = group_id, account_id, model
            run.attempts = [*run.attempts, {"account_id": str(account_id), "code": code}]

    async def previous(self, user_id, request_key, fingerprint):
        async with self.sessions.begin() as db:
            await self.billing._lock_user(db, user_id)
            await self._expire(db, user_id)
            run = await db.scalar(
                select(TextRunRecord).where(
                    TextRunRecord.user_id == user_id, TextRunRecord.request_key == request_key
                )
            )
            if run and run.fingerprint != fingerprint:
                raise HTTPException(409, "重复请求的内容不一致。")
            return Run.model_validate(run) if run else None

    async def history(self, user_id: UUID, slug: str) -> list[Run]:
        async with self.sessions.begin() as db:
            await self.billing._lock_user(db, user_id)
            await self._expire(db, user_id)
            records = await db.scalars(
                select(TextRunRecord)
                .where(TextRunRecord.user_id == user_id, TextRunRecord.tool_slug == slug)
                .order_by(TextRunRecord.created_at.desc())
                .limit(20)
            )
            return [Run.model_validate(row) for row in records]

    async def clear(self, user_id: UUID, run_id: UUID) -> None:
        async with self.sessions.begin() as db:
            await self.billing._lock_user(db, user_id)
            await self._expire(db, user_id)
            run = await db.get(TextRunRecord, run_id)
            if run is None or run.user_id != user_id:
                raise HTTPException(404, "生成记录不存在。")
            if run.status == "running":
                raise HTTPException(409, "你还有一个任务正在生成，请稍后再试。")
            # Keep the idempotency and billing receipt after the user clears generated text.
            run.output = None
