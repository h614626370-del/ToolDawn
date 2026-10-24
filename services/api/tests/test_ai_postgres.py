import asyncio
import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from test_admin_postgres import ORIGIN, admin_client, login  # noqa: F401

from tooldawn.modules.ai_tools.gateway import ModelFailure
from tooldawn.modules.ai_tools.models import TextRunRecord
from tooldawn.modules.ai_tools.schemas import RunInput
from tooldawn.modules.auth.models import UserRecord
from tooldawn.modules.billing.models import CreditRecord, WalletRecord
from tooldawn.modules.billing.schemas import AdjustmentInput
from tooldawn.modules.catalog.models import ToolRecord

pytestmark = pytest.mark.skipif(
    not os.environ.get("TOOLDAWN_TEST_DATABASE_URL"), reason="Requires migrated test PostgreSQL"
)
ENDPOINT = "/api/v1/ai-tools/text-polish/runs"


@pytest.fixture
def ai_client(admin_client):  # noqa: F811
    client, service, prefix = admin_client
    app = client.app
    app.state.model_gateway.enabled = True
    app.state.model_gateway.generate = AsyncMock(return_value="A polished result.")
    try:
        yield client, service, prefix
    finally:

        async def cleanup():
            async with service.repository.sessions.begin() as db:
                users = select(UserRecord.id).where(UserRecord.email.startswith(prefix))
                for model in (TextRunRecord, CreditRecord, WalletRecord):
                    await db.execute(delete(model).where(model.user_id.in_(users)))

        client.portal.call(cleanup)


def fund(client, user_id, amount=10):
    client.portal.call(
        client.app.state.billing.adjust,
        UUID(user_id),
        AdjustmentInput(amount=amount, reason="Test allocation", request_key=uuid4()),
        UUID(user_id),
    )


def body(**changes):
    return {"request_key": str(uuid4()), "text": "Hello world.", "style": "自然", **changes}


def test_ai_authorization_validation_setup_and_balance(ai_client):
    client, service, prefix = ai_client
    assert client.get(ENDPOINT).status_code == 401
    assert client.post(ENDPOINT, json=body(), headers=ORIGIN).status_code == 401
    login(client, service, prefix + "@example.com")
    assert client.post(ENDPOINT, json=body()).status_code == 403
    assert client.post(ENDPOINT, json=body(cost=0), headers=ORIGIN).status_code == 422
    assert client.post(ENDPOINT, json=body(style="unknown"), headers=ORIGIN).status_code == 422
    assert client.post(ENDPOINT, json=body(), headers=ORIGIN).status_code == 409
    assert client.get(ENDPOINT).json() == []
    assert client.app.state.model_gateway.generate.await_count == 0
    client.app.state.model_gateway.enabled = False
    response = client.post(ENDPOINT, json=body(), headers=ORIGIN)
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"


def test_success_retry_conflict_ownership_and_deleted_output(ai_client):
    client, service, prefix = ai_client
    user = login(client, service, prefix + "@example.com")
    fund(client, user["id"])
    data = body()
    first = client.post(ENDPOINT, json=data, headers=ORIGIN)
    assert first.status_code == 200
    run = first.json()
    assert run["status"] == "succeeded"
    assert run["output"] == "A polished result."
    assert run["cost"] == 1
    assert client.post(ENDPOINT, json=data, headers=ORIGIN).json() == run
    assert client.app.state.model_gateway.generate.await_count == 1
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 9
    assert (
        client.post(ENDPOINT, json={**data, "text": "Different input"}, headers=ORIGIN).status_code
        == 409
    )
    assert client.get(ENDPOINT).json()[0]["id"] == run["id"]
    assert "Hello world." not in client.get(ENDPOINT).text
    clear = f"/api/v1/ai-tools/runs/{run['id']}/output"
    assert client.delete(clear, headers=ORIGIN).status_code == 204
    assert client.get(ENDPOINT).json()[0]["output"] is None
    assert client.post(ENDPOINT, json=data, headers=ORIGIN).json()["output"] is None
    assert client.app.state.model_gateway.generate.await_count == 1
    login(client, service, prefix + "-other@example.com")
    assert client.get(ENDPOINT).json() == []
    assert client.delete(clear, headers=ORIGIN).status_code == 404


def test_provider_failure_refunds_exactly_once_and_can_retry(ai_client):
    client, service, prefix = ai_client
    user = login(client, service, prefix + "@example.com")
    fund(client, user["id"])
    client.app.state.model_gateway.generate.side_effect = ModelFailure("private upstream details")
    data = body()
    failed = client.post(ENDPOINT, json=data, headers=ORIGIN)
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    assert "private" not in failed.text
    assert client.post(ENDPOINT, json=data, headers=ORIGIN).json() == failed.json()
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 10
    ledger = client.get("/api/v1/billing/entries").json()["items"]
    assert sum(item["kind"] == "tool_refund" for item in ledger) == 1
    client.app.state.model_gateway.generate.side_effect = None
    assert client.post(ENDPOINT, json=body(), headers=ORIGIN).json()["status"] == "succeeded"
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 9


def test_concurrency_stale_recovery_and_late_completion(ai_client):
    client, service, prefix = ai_client
    user = login(client, service, prefix + "@example.com")
    fund(client, user["id"])
    owner = UUID(user["id"])
    repo = client.app.state.text_runs

    async def scenario():
        data = RunInput.model_validate(body())
        first, duplicate = await asyncio.gather(
            repo.prepare(owner, "text-polish", data, "test-fingerprint", 1),
            repo.prepare(owner, "text-polish", data, "test-fingerprint", 1),
        )
        assert first[0].id == duplicate[0].id
        assert sum((first[1], duplicate[1])) == 1
        with pytest.raises(HTTPException) as exc:
            await repo.prepare(
                owner, "text-polish", RunInput.model_validate(body()), "other-fingerprint", 1
            )
        assert exc.value.status_code == 409
        async with repo.sessions.begin() as db:
            await db.execute(
                update(TextRunRecord)
                .where(TextRunRecord.id == first[0].id)
                .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
        await asyncio.gather(repo.history(owner, "text-polish"), repo.history(owner, "text-polish"))
        late = await repo.finish(owner, first[0].id, "late output")
        assert late.status == "failed"
        assert late.output is None
        assert await client.app.state.billing.balance(owner) == 10
        return first[0].id

    run_id = client.portal.call(scenario)
    assert client.get(ENDPOINT).json()[0]["id"] == str(run_id)
    entries = client.get("/api/v1/billing/entries").json()["items"]
    assert sum(item["kind"] == "tool_refund" for item in entries) == 1


def test_free_generation_and_unpublished_tool_guard(ai_client):
    client, service, prefix = ai_client
    login(client, service, prefix + "@example.com")
    client.app.state.settings.ai_tool_cost = 0
    assert client.post(ENDPOINT, json=body(), headers=ORIGIN).json()["status"] == "succeeded"
    assert client.get("/api/v1/billing/entries").json()["items"] == []

    async def visibility(value):
        async with service.repository.sessions.begin() as db:
            await db.execute(
                update(ToolRecord).where(ToolRecord.slug == "text-polish").values(published=value)
            )

    try:
        client.portal.call(visibility, False)
        assert client.get("/api/v1/ai-tools/text-polish").status_code == 404
        assert client.post(ENDPOINT, json=body(), headers=ORIGIN).status_code == 404
    finally:
        client.portal.call(visibility, True)
