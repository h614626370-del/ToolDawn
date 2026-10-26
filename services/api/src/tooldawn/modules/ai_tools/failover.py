import asyncio

from tooldawn.modules.ai_tools.gateway import ModelFailure, ModelGateway

MAX_ATTEMPTS = 3
ATTEMPT_SECONDS = 30
TOTAL_SECONDS = 95


async def generate_with_group(accounts, runs, user_id, run_id, plan, tool, data):
    group_id, capability, identities = plan
    attempted = 0
    try:
        async with asyncio.timeout(TOTAL_SECONDS):
            for identity in identities:
                candidate = await accounts.group_candidate(group_id, capability, identity)
                if candidate is None:
                    continue
                revision, settings = candidate
                gateway = ModelGateway(settings)
                attempted += 1
                try:
                    failure = None
                    try:
                        async with asyncio.timeout(ATTEMPT_SECONDS):
                            output = await gateway.generate(tool, data)
                    except TimeoutError:
                        failure = ModelFailure("timeout", retryable=True)
                    except ModelFailure as exc:
                        failure = exc
                    if failure:
                        # Only controlled codes leave the gateway; upstream bodies stay private.
                        await runs.record_attempt(
                            user_id, run_id, group_id, identity, settings.llm_model, failure.code
                        )
                        if not failure.retryable:
                            raise failure
                        await accounts.mark_failure(identity, revision, failure)
                    else:
                        await runs.record_attempt(
                            user_id, run_id, group_id, identity, settings.llm_model, "succeeded"
                        )
                        return output
                finally:
                    await gateway.close()
                if attempted >= MAX_ATTEMPTS:
                    break
    except TimeoutError:
        raise ModelFailure("time_budget") from None
    raise ModelFailure("group_exhausted")
