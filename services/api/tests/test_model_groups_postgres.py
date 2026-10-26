import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy import delete, select
from test_ai_postgres import body, fund
from test_operations_postgres import ORIGIN, ops, sign_in  # noqa: F401

from tooldawn.modules.ai_tools.gateway import ModelFailure
from tooldawn.modules.ai_tools.models import TextRunRecord
from tooldawn.modules.auth.models import UserRecord
from tooldawn.modules.billing.models import CreditRecord, WalletRecord
from tooldawn.modules.catalog.models import ToolRecord
from tooldawn.modules.operations.models import ModelAccount, ModelGroup

pytestmark = pytest.mark.skipif(
    not os.environ.get("TOOLDAWN_TEST_DATABASE_URL"), reason="Requires migrated test PostgreSQL"
)
GROUPS = "/api/v1/admin/model-groups"
ENDPOINT = "/api/v1/ai-tools/text-polish/runs"


@pytest.fixture
def grouped(ops):  # noqa: F811
    client, app, prefix, _ = ops

    async def snapshot():
        async with app.state.control.sessions() as db:
            tool = await db.get(ToolRecord, "text-polish")
            return tool.model_group_id, tool.model_capability, tool.revision

    saved = client.portal.call(snapshot)
    try:
        yield client, app, prefix
    finally:

        async def cleanup():
            async with app.state.control.sessions.begin() as db:
                tool = await db.get(ToolRecord, "text-polish")
                tool.model_group_id, tool.model_capability, tool.revision = saved
                await db.flush()
                users = select(UserRecord.id).where(UserRecord.email.startswith(prefix))
                for model in (TextRunRecord, CreditRecord, WalletRecord):
                    await db.execute(delete(model).where(model.user_id.in_(users)))
                await db.execute(delete(ModelGroup).where(ModelGroup.name.startswith(prefix)))

        client.portal.call(cleanup)


def account(client, prefix, suffix="a", capabilities=None):
    result = client.post(
        "/api/v1/admin/model-accounts",
        headers=ORIGIN,
        json={
            "name": f"{prefix}-{suffix}",
            "base_url": "https://example.com/v1",
            "api_key": "private-key",
            "model": suffix,
            "capabilities": capabilities or ["text"],
        },
    )
    assert result.status_code == 200, result.text
    return result.json()


def group(client, prefix, accounts, **changes):
    result = client.post(
        GROUPS,
        headers=ORIGIN,
        json={
            "name": prefix,
            "account_ids": [a["id"] for a in accounts],
            **changes,
        },
    )
    assert result.status_code == 200, result.text
    return result.json()


def edit_group(client, row, **changes):
    data = {k: row[k] for k in ("name", "description", "enabled", "account_ids", "revision")}
    return client.put(f"{GROUPS}/{row['id']}", headers=ORIGIN, json={**data, **changes})


def bind(client, row, **changes):
    tool = next(
        t
        for t in client.get("/api/v1/admin/tools?limit=100").json()["items"]
        if t["slug"] == "text-polish"
    )
    tool.pop("updated_at")
    return client.put(
        "/api/v1/admin/tools/text-polish",
        headers=ORIGIN,
        json={
            **tool,
            "model_group_id": row["id"],
            "model_capability": "text",
            **changes,
        },
    )


def test_permissions_origin_safe_options_and_validation(grouped):
    client, app, prefix = grouped
    paths = [GROUPS, "/api/v1/admin/model-group-options"]
    for path in paths:
        assert client.get(path).status_code == 401
    sign_in(client, prefix, "user")
    for path in paths:
        assert client.get(path).status_code == 403
    actor = sign_in(client, prefix)
    a = account(client, prefix)
    g = group(client, prefix, [a])
    assert client.post(GROUPS, json={"name": prefix, "capabilities": ["text"]}).status_code == 403
    assert (
        client.post(
            GROUPS, headers=ORIGIN, json={"name": prefix, "capabilities": ["unknown"]}
        ).status_code
        == 422
    )
    assert (
        client.post(
            GROUPS,
            headers=ORIGIN,
            json={"name": prefix, "account_ids": [a["id"], a["id"]]},
        ).status_code
        == 422
    )
    assert (
        client.post(
            GROUPS,
            headers=ORIGIN,
            json={"name": prefix, "capabilities": ["image_edit"], "account_ids": [a["id"]]},
        ).status_code
        == 422
    )

    async def demote():
        async with app.state.control.sessions.begin() as db:
            (await db.get(UserRecord, UUID(actor["id"]))).is_superadmin = False

    client.portal.call(demote)
    assert client.get(GROUPS).status_code == 403
    assert edit_group(client, g).status_code == 403
    assert client.delete(f"{GROUPS}/{g['id']}?revision=1", headers=ORIGIN).status_code == 403
    assert (
        client.post(
            f"/api/v1/admin/model-accounts/{a['id']}/reset-health", headers=ORIGIN
        ).status_code
        == 403
    )
    options = client.get(paths[1])
    assert options.status_code == 200
    assert set(options.json()["items"][0]) == {"id", "name", "enabled"}
    assert "private-key" not in options.text
    assert bind(client, g).status_code == 200  # ordinary catalog admins may assign groups


def test_order_capability_filter_disabled_binding_and_revision(grouped):
    client, app, prefix = grouped
    sign_in(client, prefix)
    a = account(client, prefix, "text")
    b = account(client, prefix, "edit", ["image_edit"])
    c = account(client, prefix, "backup")
    g = group(client, prefix, [b, c, a])
    assert "capabilities" not in g
    assert bind(client, g).status_code == 200
    plan = client.portal.call(app.state.accounts.group_plan, "text-polish")
    assert [str(i) for i in plan[2]] == [c["id"], a["id"]]
    assert bind(client, g, model_capability="image_edit").status_code == 422
    assert client.delete(f"{GROUPS}/{g['id']}?revision=1", headers=ORIGIN).status_code == 409
    updated = edit_group(client, g, enabled=False)
    assert updated.status_code == 200
    assert edit_group(client, g).status_code == 409
    app.state.model_gateway.enabled = True
    app.state.model_gateway.generate = AsyncMock(return_value="must not be used")
    assert not client.get("/api/v1/ai-tools/text-polish").json()["enabled"]
    sign_in(client, prefix, "user")
    assert client.post(ENDPOINT, json=body(), headers=ORIGIN).status_code == 503
    app.state.model_gateway.generate.assert_not_awaited()


def test_failover_charges_once_tracks_account_and_retry_is_idempotent(grouped):
    client, app, prefix = grouped
    sign_in(client, prefix)
    a, b = account(client, prefix, "first"), account(client, prefix, "second")
    g = group(client, prefix, [a, b])
    assert bind(client, g).status_code == 200
    user = sign_in(client, prefix, "user")
    fund(client, user["id"])
    request = body()
    with patch("tooldawn.modules.ai_tools.failover.ModelGateway") as gateway:
        gateway.return_value.generate = AsyncMock(
            side_effect=[ModelFailure.from_status(429), "success"]
        )
        gateway.return_value.close = AsyncMock()
        response = client.post(ENDPOINT, headers=ORIGIN, json=request)
        assert response.status_code == 200, response.text
        assert response.json()["output"] == "success"
        assert gateway.return_value.generate.await_count == 2
        assert client.post(ENDPOINT, headers=ORIGIN, json=request).json() == response.json()
        assert gateway.return_value.generate.await_count == 2
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 9
    entries = client.get("/api/v1/billing/entries").json()["items"]
    assert sum(e["kind"] == "tool_usage" for e in entries) == 1
    assert "attempts" not in client.get("/api/v1/me/usage").json()["items"][0]
    sign_in(client, prefix)
    usage = client.get("/api/v1/admin/usage").json()["items"][0]
    assert usage["account_name"] == b["name"] and usage["group_name"] == prefix
    assert [a["code"] for a in usage["attempts"]] == ["rate_limited", "succeeded"]
    plan = client.portal.call(app.state.accounts.group_plan, "text-polish")
    assert [str(i) for i in plan[2]] == [b["id"]]
    assert (
        client.post(
            f"/api/v1/admin/model-accounts/{a['id']}/reset-health", headers=ORIGIN
        ).status_code
        == 200
    )
    assert len(client.portal.call(app.state.accounts.group_plan, "text-polish")[2]) == 2


@pytest.mark.parametrize("retryable,expected", [(True, 3), (False, 1)])
def test_exhaustion_refunds_once_and_rejections_do_not_retry(grouped, retryable, expected):
    client, app, prefix = grouped
    sign_in(client, prefix)
    accounts = [account(client, prefix, str(i)) for i in range(4)]
    g = group(client, prefix, accounts)
    assert bind(client, g).status_code == 200
    user = sign_in(client, prefix, "user")
    fund(client, user["id"])
    request = body()
    with patch("tooldawn.modules.ai_tools.failover.ModelGateway") as gateway:
        gateway.return_value.generate = AsyncMock(
            side_effect=ModelFailure("request_rejected", retryable=retryable)
        )
        gateway.return_value.close = AsyncMock()
        response = client.post(ENDPOINT, headers=ORIGIN, json=request)
        assert response.json()["status"] == "failed"
        assert gateway.return_value.generate.await_count == expected
        assert client.post(ENDPOINT, headers=ORIGIN, json=request).json() == response.json()
        assert gateway.return_value.generate.await_count == expected
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 10
    entries = client.get("/api/v1/billing/entries").json()["items"]
    assert sum(e["kind"] == "tool_usage" for e in entries) == 1
    assert sum(e["kind"] == "tool_refund" for e in entries) == 1


def test_cooldown_shared_across_groups_expiry_and_revision_guard(grouped):
    client, app, prefix = grouped
    actor = sign_in(client, prefix)
    a = account(client, prefix)
    first = group(client, prefix + "-first", [a])
    second = group(client, prefix + "-second", [a])
    assert bind(client, first).status_code == 200
    failure = ModelFailure.from_status(401)
    client.portal.call(app.state.accounts.mark_failure, UUID(a["id"]), a["revision"], failure)
    assert not client.portal.call(app.state.accounts.group_plan, "text-polish")[2]
    assert bind(client, second).status_code == 200
    assert not client.portal.call(app.state.accounts.group_plan, "text-polish")[2]

    async def expire():
        async with app.state.control.sessions.begin() as db:
            (await db.get(ModelAccount, UUID(a["id"]))).cooldown_until = datetime.now(
                UTC
            ) - timedelta(seconds=1)

    client.portal.call(expire)
    assert client.portal.call(app.state.accounts.group_plan, "text-polish")[2]
    client.portal.call(app.state.accounts.reset_health, UUID(a["id"]), UUID(actor["id"]))
    client.portal.call(app.state.accounts.mark_failure, UUID(a["id"]), a["revision"], failure)
    assert client.portal.call(app.state.accounts.group_plan, "text-polish")[2]
    assert client.delete(f"{GROUPS}/{first['id']}?revision=1", headers=ORIGIN).status_code == 200


def test_empty_group_does_not_use_environment_gateway(grouped):
    client, app, prefix = grouped
    sign_in(client, prefix)
    g = group(client, prefix, [])
    assert bind(client, g).status_code == 200
    app.state.model_gateway.enabled = True
    app.state.model_gateway.generate = AsyncMock()
    sign_in(client, prefix, "user")
    assert client.post(ENDPOINT, headers=ORIGIN, json=body()).status_code == 503
    app.state.model_gateway.generate.assert_not_awaited()


def test_account_models_control_routing_without_group_restrictions(grouped):
    client, app, prefix = grouped
    sign_in(client, prefix)
    a = account(client, prefix, "default", ["text", "image_edit"])
    payload = {
        key: a[key] for key in ("name", "base_url", "model", "capabilities", "enabled", "revision")
    }
    response = client.put(
        f"/api/v1/admin/model-accounts/{a['id']}",
        headers=ORIGIN,
        json={
            **payload,
            "capability_models": {"text": "writing-model", "image_edit": "image-model"},
        },
    )
    assert response.status_code == 200, response.text
    b = account(client, prefix, "vision", ["vision"])
    g = group(client, prefix, [b, a])
    assert "capabilities" not in g
    assert bind(client, g).status_code == 200
    plan = client.portal.call(app.state.accounts.group_plan, "text-polish")
    assert [str(i) for i in plan[2]] == [a["id"]]
    resolved = client.portal.call(
        app.state.accounts.group_candidate, UUID(g["id"]), "image_edit", UUID(a["id"])
    )
    assert resolved[1].llm_model == "image-model"
    user = sign_in(client, prefix, "user")
    fund(client, user["id"])
    with patch("tooldawn.modules.ai_tools.failover.ModelGateway") as gateway:
        gateway.return_value.generate = AsyncMock(return_value="done")
        gateway.return_value.close = AsyncMock()
        result = client.post(ENDPOINT, headers=ORIGIN, json=body())
        assert result.json()["status"] == "succeeded"
        assert gateway.call_args.args[0].llm_model == "writing-model"


def test_model_discovery_permissions_existing_key_and_revision(grouped):
    client, app, prefix = grouped
    path = "/api/v1/admin/model-accounts/models"
    payload = {"base_url": "https://example.com/v1", "api_key": "private-key"}
    assert client.post(path, headers=ORIGIN, json=payload).status_code == 401
    sign_in(client, prefix, "user")
    assert client.post(path, headers=ORIGIN, json=payload).status_code == 403
    actor = sign_in(client, prefix)
    a = account(client, prefix)
    existing = {"base_url": a["base_url"], "account_id": a["id"], "revision": a["revision"]}
    assert client.post(path, json=payload).status_code == 403
    with patch.object(
        app.state.accounts,
        "fetch_models",
        new=AsyncMock(return_value=["text-model", "image-model"]),
    ) as fetch:
        result = client.post(path, headers=ORIGIN, json=existing)
        assert result.status_code == 200 and result.json()["items"] == ["text-model", "image-model"]
        assert "private-key" not in result.text
        fetch.assert_awaited_once_with(a["base_url"], "private-key")
        assert (
            client.post(path, headers=ORIGIN, json={**existing, "revision": 0}).status_code == 409
        )
        assert fetch.await_count == 1
        assert (
            client.post(path, headers=ORIGIN, json={"base_url": a["base_url"]}).status_code == 422
        )
        assert client.post(path, headers=ORIGIN, json=payload).status_code == 200

    async def demote():
        async with app.state.control.sessions.begin() as db:
            (await db.get(UserRecord, UUID(actor["id"]))).is_superadmin = False

    client.portal.call(demote)
    assert client.post(path, headers=ORIGIN, json=existing).status_code == 403
