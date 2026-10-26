import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import load_only

from tooldawn.modules.ai_tools.models import TextRunRecord
from tooldawn.modules.ai_tools.repository import TextRunRepository
from tooldawn.modules.image_tools.models import ImageJob, ImageReference
from tooldawn.modules.image_tools.schemas import run_view

SLUG = "image-generate"


class ImageRepository:
    def __init__(self, billing, box):
        self.billing, self.box = billing, box
        self.sessions = billing.sessions
        self.runs = TextRunRepository(billing)

    async def prepare(self, user_id, data, fingerprint, cost, group_id):
        async with self.sessions.begin() as db:
            owner = await self.billing._lock_user(db, user_id)
            if owner.disabled:
                raise HTTPException(403, "账户已禁用。")
            await self.runs._expire(db, user_id)
            previous = await db.scalar(
                select(TextRunRecord).where(
                    TextRunRecord.user_id == user_id, TextRunRecord.request_key == data.request_key
                )
            )
            if previous:
                if previous.fingerprint != fingerprint:
                    raise HTTPException(409, "重复请求的内容不一致。")
                return run_view(previous, await db.get(ImageJob, previous.id))
            if await db.scalar(
                select(TextRunRecord.id)
                .where(TextRunRecord.user_id == user_id, TextRunRecord.status == "running")
                .limit(1)
            ):
                raise HTTPException(409, "你还有一个任务正在生成，请稍后再试。")
            now = datetime.now(UTC)
            payload = data.model_dump(mode="json", exclude={"request_key", "reference_id"})
            if data.reference_id:
                reference = await db.get(ImageReference, data.reference_id)
                if not reference or reference.user_id != user_id or reference.expires_at <= now:
                    raise HTTPException(422, "参考图片已过期，请重新上传。")
                payload["reference_base64"] = self.box.decrypt(reference.encrypted_image)
            run = TextRunRecord(
                id=uuid4(),
                user_id=user_id,
                request_key=data.request_key,
                fingerprint=fingerprint,
                tool_slug=SLUG,
                status="running",
                cost=cost,
                language="zh",
                created_at=now,
                expires_at=now + timedelta(seconds=660),
                group_id=group_id,
                attempts=[],
            )
            if cost:
                await self.billing._apply(db, user_id, -cost, "tool_usage", f"tool:{run.id}", SLUG)
            db.add(run)
            await db.flush()
            job = ImageJob(
                run_id=run.id,
                payload=self.box.encrypt(json.dumps(payload, ensure_ascii=False)),
                options=data.model_dump(include={"mode", "size", "background", "quality"}),
            )
            db.add(job)
            return run_view(run, job)

    async def previous(self, user_id, request_key, fingerprint):
        run = await self.runs.previous(user_id, request_key, fingerprint)
        if not run:
            return None
        async with self.sessions() as db:
            return run_view(run, await db.get(ImageJob, run.id))

    async def history(self, user_id):
        runs = await self.runs.history(user_id, SLUG)
        async with self.sessions() as db:
            jobs = {
                j.run_id: j
                for j in await db.scalars(
                    select(ImageJob)
                    .options(load_only(ImageJob.run_id, ImageJob.options))
                    .where(ImageJob.run_id.in_([r.id for r in runs]))
                )
            }
            return [run_view(r, jobs.get(r.id)) for r in runs]

    async def upload(self, user_id, normalized):
        image, width, height = normalized
        now = datetime.now(UTC)
        async with self.sessions.begin() as db:
            owner = await self.billing._lock_user(db, user_id)
            if owner.disabled:
                raise HTTPException(403, "账户已禁用。")
            await db.execute(
                delete(ImageReference).where(
                    ImageReference.user_id == user_id, ImageReference.expires_at <= now
                )
            )
            count = await db.scalar(
                select(func.count())
                .select_from(ImageReference)
                .where(ImageReference.user_id == user_id)
            )
            if count >= 8:
                raise HTTPException(429, "暂存图片过多，请移除不用的参考图后重试。")
            reference = ImageReference(
                id=uuid4(),
                user_id=user_id,
                encrypted_image=self.box.encrypt(image),
                width=width,
                height=height,
                expires_at=now + timedelta(hours=1),
            )
            db.add(reference)
            return {
                "id": reference.id,
                "width": width,
                "height": height,
                "expires_at": reference.expires_at,
            }

    async def remove_reference(self, user_id, reference_id):
        async with self.sessions.begin() as db:
            await self.billing._lock_user(db, user_id)
            reference = await db.get(ImageReference, reference_id)
            if reference is None or reference.user_id != user_id:
                raise HTTPException(404, "参考图片不存在。")
            await db.delete(reference)

    async def claim(self):
        async with self.sessions.begin() as db:
            job = await db.scalar(
                select(ImageJob)
                .join(TextRunRecord)
                .where(
                    ImageJob.claimed.is_(False),
                    TextRunRecord.status == "running",
                    TextRunRecord.expires_at > datetime.now(UTC),
                )
                .order_by(TextRunRecord.created_at)
                .with_for_update(skip_locked=True, of=ImageJob)
                .limit(1)
            )
            if not job:
                return None
            job.claimed = True
            run = await db.get(TextRunRecord, job.run_id)
            return run.id, run.user_id, run.group_id, job.payload

    async def complete(self, user_id, run_id, image=None):
        async with self.sessions.begin() as db:
            await self.billing._lock_user(db, user_id)
            run = await db.get(TextRunRecord, run_id)
            job = await db.get(ImageJob, run_id, with_for_update=True)
            if not run or run.user_id != user_id or not job:
                raise HTTPException(404, "生成记录不存在。")
            job.payload = None
            if run.status != "running":
                return
            if image is not None and run.expires_at > datetime.now(UTC):
                job.image, job.media_type = image, "image/png"
                run.status = "succeeded"
                run.output = f"/api/v1/image-tools/runs/{run.id}/image"
                self.runs._complete(run)
            else:
                await self.runs._fail(db, run)

    async def recover(self):
        # A crashed claimed request may have reached the provider: expire/refund, never replay it.
        async with self.sessions() as db:
            rows = (
                await db.execute(
                    select(TextRunRecord.id, TextRunRecord.user_id)
                    .join(ImageJob)
                    .where(
                        TextRunRecord.status == "running",
                        TextRunRecord.expires_at <= datetime.now(UTC),
                    )
                    .limit(100)
                )
            ).all()
        for run_id, user_id in rows:
            await self.complete(user_id, run_id)
        async with self.sessions.begin() as db:
            from sqlalchemy import update

            await db.execute(
                delete(ImageReference).where(ImageReference.expires_at <= datetime.now(UTC))
            )

            await db.execute(
                update(ImageJob)
                .where(
                    ImageJob.payload.is_not(None),
                    ImageJob.run_id.in_(
                        select(TextRunRecord.id).where(TextRunRecord.status != "running")
                    ),
                )
                .values(payload=None)
            )

    async def image(self, user_id, run_id, delete=False):
        async with self.sessions.begin() as db:
            await self.billing._lock_user(db, user_id)
            run = await db.get(TextRunRecord, run_id)
            job = await db.get(ImageJob, run_id)
            if not run or run.user_id != user_id or not job or run.status != "succeeded":
                raise HTTPException(404, "生成记录不存在。")
            if delete:
                job.image, run.output = None, None
                return None
            if not job.image or not run.output:
                raise HTTPException(404, "生成记录不存在。")
            return job.image
