"""Run with python -m tooldawn.image_worker. PostgreSQL is the durable queue."""

import asyncio
import json
import logging

from tooldawn.config import Settings
from tooldawn.infra.database import create_database
from tooldawn.modules.ai_tools.gateway import ModelFailure
from tooldawn.modules.billing.repository import BillingRepository
from tooldawn.modules.image_tools.gateway import generate_image
from tooldawn.modules.image_tools.repository import SLUG, ImageRepository
from tooldawn.modules.operations.accounts import AccountRepository
from tooldawn.modules.operations.settings import SettingsRepository

log = logging.getLogger(__name__)


async def process_one(repo, accounts, generate=generate_image):
    await repo.recover()
    job = await repo.claim()
    if not job:
        return False
    run_id, user_id, group_id, encrypted = job
    result = None
    try:
        payload = json.loads(repo.box.decrypt(encrypted))
        config = await accounts.control.current()
        override = config.tool_overrides.get(SLUG)
        if not config.ai_enabled or (override and not override.enabled):
            await repo.complete(user_id, run_id)
            return True
        capability = "image_edit" if payload.get("mode") == "edit" else "image_generate"
        plan = await accounts.group_plan(SLUG, capability)
        if plan and plan[0] == group_id and plan[1] == capability:
            async with asyncio.timeout(550):
                for identity in plan[2][:3]:
                    candidate = await accounts.group_candidate(group_id, capability, identity)
                    if not candidate:
                        continue
                    revision, settings = candidate
                    try:
                        result = await generate(settings, payload)
                        await repo.runs.record_attempt(
                            user_id, run_id, group_id, identity, settings.llm_model, "succeeded"
                        )
                        break
                    except ModelFailure as failure:
                        await repo.runs.record_attempt(
                            user_id, run_id, group_id, identity, settings.llm_model, failure.code
                        )
                        if failure.retryable:
                            await accounts.mark_failure(identity, revision, failure)
                        else:
                            break
    except asyncio.CancelledError:
        await asyncio.shield(repo.complete(user_id, run_id))
        raise
    except Exception:
        # Never log request/response bodies, prompts, or decrypted credentials.
        log.warning("Image task failed: %s", run_id)
    await repo.complete(user_id, run_id, result)
    return True


async def main():
    settings = Settings()
    engine, sessions = create_database(settings.database_url)
    control = SettingsRepository(sessions, settings)
    repo = ImageRepository(BillingRepository(sessions), control.box)
    accounts = AccountRepository(control)
    try:
        while True:
            try:
                if await process_one(repo, accounts):
                    continue
            except Exception:
                log.warning("Image worker temporarily unavailable; retrying")
            await asyncio.sleep(2)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
