import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from tooldawn.modules.ai_tools.failover import generate_with_group
from tooldawn.modules.ai_tools.gateway import ModelFailure


@pytest.mark.parametrize(
    "status,retryable",
    [
        (400, False),
        (401, True),
        (403, True),
        (404, True),
        (422, False),
        (429, True),
        (500, True),
        (503, True),
    ],
)
def test_status_classification(status, retryable):
    error = ModelFailure.from_status(status, "999999")
    assert error.retryable is retryable
    assert error.cooldown <= 300


def test_timeouts_are_bounded_and_close_clients():
    async def scenario():
        accounts = SimpleNamespace(
            group_candidate=AsyncMock(return_value=(1, SimpleNamespace(llm_model="model"))),
            mark_failure=AsyncMock(),
        )
        runs = SimpleNamespace(record_attempt=AsyncMock())

        async def slow(*args):
            await asyncio.sleep(1)

        with (
            patch("tooldawn.modules.ai_tools.failover.ATTEMPT_SECONDS", 0.01),
            patch("tooldawn.modules.ai_tools.failover.ModelGateway") as gateway,
        ):
            gateway.return_value.generate = AsyncMock(side_effect=slow)
            gateway.return_value.close = AsyncMock()
            with pytest.raises(ModelFailure):
                await generate_with_group(
                    accounts, runs, "user", "run", ("group", "text", [1, 2, 3, 4]), None, None
                )
            assert gateway.return_value.generate.await_count == 3
            assert gateway.return_value.close.await_count == 3
            assert accounts.mark_failure.await_count == 3

    asyncio.run(scenario())


def test_total_budget_stops_attempts():
    async def scenario():
        accounts = SimpleNamespace(group_candidate=AsyncMock(side_effect=lambda *args: None))

        async def stalled(*args):
            await asyncio.sleep(1)

        accounts.group_candidate.side_effect = stalled
        with patch("tooldawn.modules.ai_tools.failover.TOTAL_SECONDS", 0.01):
            with pytest.raises(ModelFailure, match="time_budget"):
                await generate_with_group(
                    accounts, None, "u", "r", ("g", "text", [1, 2]), None, None
                )
        assert accounts.group_candidate.await_count == 1

    asyncio.run(scenario())
