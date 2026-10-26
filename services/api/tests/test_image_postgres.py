import asyncio
import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from test_ai_postgres import fund
from test_image_gateway import PNG, reference_png
from test_model_groups_postgres import account, group
from test_operations_postgres import ORIGIN, ops, sign_in  # noqa: F401

from tooldawn.image_worker import process_one
from tooldawn.modules.ai_tools.gateway import ModelFailure
from tooldawn.modules.ai_tools.models import TextRunRecord
from tooldawn.modules.auth.models import UserRecord
from tooldawn.modules.billing.models import CreditRecord, WalletRecord
from tooldawn.modules.catalog.models import ToolRecord
from tooldawn.modules.image_tools.models import ImageJob, ImageReference
from tooldawn.modules.operations.models import ModelAccount, ModelGroup

pytestmark = pytest.mark.skipif(
    not os.environ.get("TOOLDAWN_TEST_DATABASE_URL"), reason="Requires migrated test PostgreSQL"
)
ENDPOINT = "/api/v1/image-tools/image-generate/runs"


@pytest.fixture
def image_client(ops):  # noqa: F811
    client, app, prefix, _ = ops

    async def snapshot():
        async with app.state.control.sessions() as db:
            tool = await db.get(ToolRecord, "image-generate")
            return tool.model_group_id, tool.model_capability, tool.revision

    saved = client.portal.call(snapshot)
    sign_in(client, prefix)
    a = account(client, prefix, "image-a", ["image_generate"])
    b = account(client, prefix, "image-b", ["image_generate"])
    g = group(client, prefix, [a, b])

    async def bind():
        async with app.state.control.sessions.begin() as db:
            tool = await db.get(ToolRecord, "image-generate")
            tool.model_group_id = UUID(g["id"])
            tool.model_capability = "image_generate"

    client.portal.call(bind)
    client.cookies.clear()
    try:
        yield client, app, prefix
    finally:

        async def cleanup():
            async with app.state.control.sessions.begin() as db:
                tool = await db.get(ToolRecord, "image-generate")
                tool.model_group_id, tool.model_capability, tool.revision = saved
                await db.flush()
                users = select(UserRecord.id).where(UserRecord.email.startswith(prefix))
                for model in (TextRunRecord, CreditRecord, WalletRecord):
                    await db.execute(delete(model).where(model.user_id.in_(users)))
                await db.execute(delete(ModelGroup).where(ModelGroup.name.startswith(prefix)))

        client.portal.call(cleanup)


def body(**changes):
    return {"request_key": str(uuid4()), "prompt": "Private watercolor cat prompt", **changes}


def test_reference_owner_expiry_snapshot_edit_routing_and_quality(image_client):
    client, app, prefix = image_client
    upload_url = "/api/v1/image-tools/references"
    assert client.post(upload_url, headers=ORIGIN, content=reference_png()).status_code == 401
    user = sign_in(client, prefix, "user")
    fund(client, user["id"])
    assert client.post(upload_url, content=reference_png()).status_code == 403
    assert client.post(upload_url, headers=ORIGIN, content=b"<svg/>").status_code == 422
    ref = client.post(upload_url, headers=ORIGIN, content=reference_png()).json()
    assert ref["width"] == 16
    data = body(mode="edit", reference_id=ref["id"], quality="high", background="transparent")
    # A generation account alone cannot serve edits.
    assert client.post(ENDPOINT, headers=ORIGIN, json=data).status_code == 503

    async def enable_edit():
        async with app.state.control.sessions.begin() as db:
            row = await db.scalar(
                select(ModelAccount).where(ModelAccount.name == f"{prefix}-image-b")
            )
            row.capabilities = ["image_generate", "image_edit"]
            row.capability_models = {"image_edit": "mapped-edit-model"}

    client.portal.call(enable_edit)
    for role in ("other", "admin"):
        sign_in(client, prefix, role)
        assert client.delete(f"{upload_url}/{ref['id']}", headers=ORIGIN).status_code == 404
        assert client.post(ENDPOINT, headers=ORIGIN, json=data).status_code == 422

    async def regular_admin():
        async with app.state.control.sessions.begin() as db:
            row = await db.scalar(
                select(UserRecord).where(UserRecord.email == f"{prefix}-other@example.com")
            )
            row.role = "admin"
            row.is_superadmin = False

    client.portal.call(regular_admin)
    sign_in(client, prefix, "other")
    assert client.delete(f"{upload_url}/{ref['id']}", headers=ORIGIN).status_code == 404
    assert client.post(ENDPOINT, headers=ORIGIN, json=data).status_code == 422
    sign_in(client, prefix, "user")
    result = client.post(ENDPOINT, headers=ORIGIN, json=data)
    assert result.status_code == 200, result.text
    run = result.json()
    assert run["cost"] == 4 and run["mode"] == "edit" and run["quality"] == "high"
    assert client.post(ENDPOINT, headers=ORIGIN, json=data).json() == run
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 6
    assert client.delete(f"{upload_url}/{ref['id']}", headers=ORIGIN).status_code == 204

    async def generated(settings, payload):
        assert settings.llm_model == "mapped-edit-model"
        assert payload["reference_base64"] and payload["mode"] == "edit"
        return reference_png()

    client.portal.call(process_one, app.state.image_runs, app.state.accounts, generated)
    assert client.get(ENDPOINT).json()[0]["status"] == "succeeded"
    ref = client.post(upload_url, headers=ORIGIN, content=reference_png()).json()

    async def expire():
        async with app.state.control.sessions.begin() as db:
            row = await db.get(ImageReference, UUID(ref["id"]))
            assert "private reference metadata" not in row.encrypted_image
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            job = await db.get(ImageJob, UUID(run["id"]))
            assert job.payload is None

    client.portal.call(expire)
    assert (
        client.post(
            ENDPOINT, headers=ORIGIN, json=body(mode="edit", reference_id=ref["id"])
        ).status_code
        == 422
    )
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 6
    failed = client.post(
        ENDPOINT, headers=ORIGIN, json=body(quality="high", background="transparent")
    )
    assert failed.status_code == 200
    client.portal.call(
        process_one,
        app.state.image_runs,
        app.state.accounts,
        AsyncMock(side_effect=ModelFailure("transparency_missing")),
    )
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 6


def test_permissions_input_idempotency_ownership_and_deletion(image_client):
    client, app, prefix = image_client
    assert client.get(ENDPOINT).status_code == 401
    assert client.post(ENDPOINT, headers=ORIGIN, json=body()).status_code == 401
    assert client.get("/api/v1/image-tools/image-generate").json()["enabled"]
    user = sign_in(client, prefix, "user")
    assert client.post(ENDPOINT, json=body()).status_code == 403
    assert client.post(ENDPOINT, headers=ORIGIN, json=body(size="100000x100000")).status_code == 422
    assert client.post(ENDPOINT, headers=ORIGIN, json=body(cost=0)).status_code == 422
    assert client.post(ENDPOINT, headers=ORIGIN, json=body()).status_code == 409
    fund(client, user["id"])
    data = body()
    run = client.post(ENDPOINT, headers=ORIGIN, json=data).json()
    assert run["status"] == "running"
    assert client.post(ENDPOINT, headers=ORIGIN, json=data).json() == run
    assert (
        client.post(ENDPOINT, headers=ORIGIN, json={**data, "prompt": "Other"}).status_code == 409
    )
    assert client.post(ENDPOINT, headers=ORIGIN, json=body()).status_code == 409
    identity = UUID(run["id"])

    async def stored():
        async with app.state.control.sessions() as db:
            return await db.get(ImageJob, identity)

    job = client.portal.call(stored)
    assert data["prompt"] not in job.payload
    assert data["prompt"] in app.state.control.box.decrypt(job.payload)
    mock = AsyncMock(return_value=PNG)
    assert client.portal.call(process_one, app.state.image_runs, app.state.accounts, mock)
    assert mock.await_count == 1
    result = client.get(ENDPOINT).json()[0]
    assert result["status"] == "succeeded"
    assert data["prompt"] not in client.get(ENDPOINT).text
    assert client.portal.call(stored).payload is None
    assert client.get(result["output"]).content == PNG
    assert (
        "attachment"
        in client.get(result["output"] + "?download=true").headers["content-disposition"]
    )
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 9
    assert client.post(ENDPOINT, headers=ORIGIN, json=data).json() == result
    sign_in(client, prefix, "other")
    assert client.get(result["output"]).status_code == 404
    assert client.delete(result["output"], headers=ORIGIN).status_code == 404
    sign_in(client, prefix)
    assert client.get(result["output"]).status_code == 404  # Superadmin is not the owner.
    sign_in(client, prefix, "user")
    assert (
        client.delete(f"/api/v1/ai-tools/runs/{identity}/output", headers=ORIGIN).status_code == 204
    )
    assert client.portal.call(stored).image is None
    assert client.get(result["output"]).status_code == 404


def test_failover_and_single_refund(image_client):
    client, app, prefix = image_client
    user = sign_in(client, prefix, "user")
    fund(client, user["id"])
    run = client.post(ENDPOINT, headers=ORIGIN, json=body()).json()
    mock = AsyncMock(side_effect=[ModelFailure.from_status(429), PNG])
    client.portal.call(process_one, app.state.image_runs, app.state.accounts, mock)
    assert mock.await_count == 2
    assert client.get(ENDPOINT).json()[0]["status"] == "succeeded"
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 9
    failed = client.post(ENDPOINT, headers=ORIGIN, json=body()).json()
    client.portal.call(
        process_one,
        app.state.image_runs,
        app.state.accounts,
        AsyncMock(side_effect=ModelFailure("request_rejected")),
    )
    assert client.get(ENDPOINT).json()[0]["status"] == "failed"
    client.portal.call(app.state.image_runs.complete, UUID(user["id"]), UUID(failed["id"]))
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 9
    assert run["id"] != failed["id"]


def test_concurrent_claim_and_crash_recovery(image_client):
    client, app, prefix = image_client
    user = sign_in(client, prefix, "user")
    fund(client, user["id"])
    data = body()
    run = client.post(ENDPOINT, headers=ORIGIN, json=data).json()

    async def claim():
        return await asyncio.gather(app.state.image_runs.claim(), app.state.image_runs.claim())

    claims = client.portal.call(claim)
    assert sum(c is not None for c in claims) == 1

    async def expire():
        async with app.state.control.sessions.begin() as db:
            row = await db.get(TextRunRecord, UUID(run["id"]))
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    client.portal.call(expire)
    mock = AsyncMock(return_value=PNG)
    assert not client.portal.call(process_one, app.state.image_runs, app.state.accounts, mock)
    assert mock.await_count == 0  # An ambiguous dispatched job must never be replayed.
    assert client.get(ENDPOINT).json()[0]["status"] == "failed"
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 10
    client.portal.call(app.state.image_runs.complete, UUID(user["id"]), UUID(run["id"]), PNG)
    assert client.get(ENDPOINT).json()[0]["status"] == "failed"
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 10
