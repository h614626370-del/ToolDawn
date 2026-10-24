import asyncio
import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from test_operations_postgres import ORIGIN, ops, settings_input, sign_in  # noqa: F401
from test_payment_providers import config, keys, signed_event  # noqa: F401

from tooldawn.modules.auth.models import UserRecord
from tooldawn.modules.billing.models import CreditRecord, OrderRecord, ProviderRecord, WalletRecord
from tooldawn.modules.billing.provider_config import CATALOG
from tooldawn.modules.billing.provider_gateway import PaymentLink, ProviderGateway
from tooldawn.modules.billing.providers import ProviderRepository

pytestmark = pytest.mark.skipif(
    not os.environ.get("TOOLDAWN_TEST_DATABASE_URL"), reason="Requires migrated test PostgreSQL"
)


@pytest.fixture
def payment_env(ops):  # noqa: F811
    client, app, prefix, settings = ops
    yield client, app, prefix, settings

    async def cleanup():
        async with app.state.control.sessions.begin() as db:
            users = select(UserRecord.id).where(UserRecord.email.startswith(prefix))
            for model in (CreditRecord, WalletRecord, OrderRecord):
                await db.execute(delete(model).where(model.user_id.in_(users)))
            await db.execute(delete(ProviderRecord).where(ProviderRecord.name.startswith(prefix)))

    client.portal.call(cleanup)


def payload(kind, prefix, key_pair):
    cfg = config(kind, key_pair)
    return dict(
        name=prefix + "-" + kind,
        kind=kind,
        enabled=True,
        sort_order=0,
        methods=CATALOG[kind]["methods"],
        config={field["key"]: cfg[field["key"]] for field in CATALOG[kind]["fields"]},
    )


def test_provider_permissions_secret_storage_drafts_and_revision(payment_env, keys):  # noqa: F811
    client, app, prefix, _ = payment_env
    url = "/api/v1/admin/billing/providers"
    data = payload("easypay", prefix, keys)
    for role, expected in ((None, 401), ("user", 403), ("other", 403), ("admin", 200)):
        if role:
            actor = sign_in(client, prefix, role)
            if role == "other":

                async def promote(actor_id=actor["id"]):
                    async with app.state.control.sessions.begin() as db:
                        (await db.get(UserRecord, UUID(actor_id))).role = "admin"

                client.portal.call(promote)
        assert client.get(url).status_code == expected
        assert client.get("/api/v1/admin/billing/provider-types").status_code == expected
        result = client.post(url, json=data, headers=ORIGIN)
        assert result.status_code == expected, result.text
    row = result.json()
    assert "test-only-pkey" not in result.text and "key" not in row["config"]
    assert row["secrets_set"]["key"]
    assert client.post(url, json=data).status_code == 403
    assert (
        client.post(url, json={**data, "config": {"unknown": "x"}}, headers=ORIGIN).status_code
        == 422
    )
    identity = row["id"]
    keep = {**data, "revision": row["revision"], "config": {"key": None}}
    result = client.put(url + "/" + identity, json=keep, headers=ORIGIN)
    assert result.status_code == 200 and result.json()["secrets_set"]["key"]
    assert client.put(url + "/" + identity, json=keep, headers=ORIGIN).status_code == 409
    public = client.get("/api/v1/billing/methods")
    assert "config" not in public.text and "test-only-pkey" not in public.text

    async def stored():
        async with app.state.control.sessions() as db:
            return (await db.get(ProviderRecord, UUID(identity))).config

    assert "test-only-pkey" not in client.portal.call(stored)
    # Disabled instances can be incomplete and are never advertised to users.
    draft = {**data, "name": prefix + "-draft", "enabled": False, "config": {}}
    saved = client.post(url, json=draft, headers=ORIGIN)
    assert saved.status_code == 200
    assert all(
        item["id"] != saved.json()["id"]
        for item in client.get("/api/v1/billing/methods").json()["items"]
    )
    assert (
        client.delete(
            url + "/" + saved.json()["id"], params={"revision": 1}, headers=ORIGIN
        ).status_code
        == 200
    )


def test_all_channels_complete_only_after_signed_notification(payment_env, keys, monkeypatch):  # noqa: F811
    client, app, prefix, _ = payment_env
    sign_in(client, prefix)
    packages = [{"id": "cny-pack", "credits": 100, "unit_amount": 500, "currency": "cny"}]
    result = client.put(
        "/api/v1/admin/settings",
        json=settings_input(client, credit_packages=packages),
        headers=ORIGIN,
    )
    assert result.status_code == 200
    rows = {}
    for kind in CATALOG:
        result = client.post(
            "/api/v1/admin/billing/providers", json=payload(kind, prefix, keys), headers=ORIGIN
        )
        assert result.status_code == 200, result.text
        rows[kind] = result.json()
    original = ProviderGateway.checkout

    async def upstream(adapter, record):
        if adapter.kind in {"easypay", "alipay"}:
            return await original(adapter, record)
        if adapter.kind == "wxpay":
            return PaymentLink(qr_code="weixin://wxpay/test")
        return PaymentLink(url="https://pay.airwallex.com/test", checkout_id=f"trade-{record.id}")

    monkeypatch.setattr(ProviderGateway, "checkout", upstream)
    user = sign_in(client, prefix, "user")
    orders = {}
    for kind, provider in rows.items():
        body = {
            "package_id": "cny-pack",
            "request_key": str(uuid4()),
            "provider_id": provider["id"],
            "payment_method": provider["methods"][0],
        }
        response = client.post("/api/v1/billing/checkout", json=body, headers=ORIGIN)
        assert response.status_code == 200, response.text
        orders[kind] = response.json()["order_id"]
        assert (
            client.post("/api/v1/billing/checkout", json=body, headers=ORIGIN).json()
            == response.json()
        )
        # Provider selection is part of idempotency; a request key cannot switch merchants.
        assert (
            client.post(
                "/api/v1/billing/checkout",
                json={**body, "provider_id": str(uuid4())},
                headers=ORIGIN,
            ).status_code
            == 409
        )
        assert (
            client.post(f"/api/v1/billing/orders/{orders[kind]}/resume", headers=ORIGIN).status_code
            == 200
        )
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 0
    sign_in(client, prefix, "other")
    for identity in orders.values():
        assert client.get(f"/api/v1/billing/orders/{identity}").status_code == 404
        assert (
            client.post(f"/api/v1/billing/orders/{identity}/resume", headers=ORIGIN).status_code
            == 404
        )
    for kind, identity in orders.items():
        cfg = config(kind, keys)
        url = f"/api/v1/billing/providers/{rows[kind]['id']}/webhook"
        wrong, headers = signed_event(
            kind, cfg, UUID(identity), amount=1, trade_id=f"trade-{identity}"
        )
        assert client.post(url, content=wrong, headers=headers).status_code == 400
        body, headers = signed_event(kind, cfg, UUID(identity), trade_id=f"trade-{identity}")
        assert client.post(url, content=body + b"tampered", headers=headers).status_code == 400
        for _ in range(2):
            response = client.post(url, content=body, headers=headers)
            assert response.status_code == 200, response.text
    sign_in(client, prefix, "user")
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 500
    assert client.get("/api/v1/billing/entries").json()["total"] == 5
    assert all(
        item["status"] == "paid" for item in client.get("/api/v1/billing/orders").json()["items"]
    )
    assert (
        client.post(f"/api/v1/billing/orders/{orders['wxpay']}/resume", headers=ORIGIN).status_code
        == 409
    )
    assert user["id"]


def test_instance_lock_disable_and_concurrent_notifications(payment_env, keys):  # noqa: F811
    client, app, prefix, _ = payment_env
    actor = sign_in(client, prefix)
    data = payload("easypay", prefix, keys)
    provider = client.post("/api/v1/admin/billing/providers", json=data, headers=ORIGIN).json()
    packages = [{"id": "cny-pack", "credits": 100, "unit_amount": 500, "currency": "cny"}]
    client.put(
        "/api/v1/admin/settings",
        json=settings_input(client, credit_packages=packages),
        headers=ORIGIN,
    )
    identity = client.post(
        "/api/v1/billing/checkout",
        json={
            "package_id": "cny-pack",
            "request_key": str(uuid4()),
            "provider_id": provider["id"],
            "payment_method": "alipay",
        },
        headers=ORIGIN,
    ).json()["order_id"]
    url = "/api/v1/admin/billing/providers/" + provider["id"]
    assert (
        client.put(
            url, json={**data, "revision": 1, "config": {"key": "changed"}}, headers=ORIGIN
        ).status_code
        == 409
    )
    assert client.delete(url, params={"revision": 1}, headers=ORIGIN).status_code == 409
    response = client.put(url, json={**data, "revision": 1, "enabled": False}, headers=ORIGIN)
    assert response.status_code == 200 and response.json()["config_locked"]
    assert (
        client.post(
            "/api/v1/billing/checkout",
            json={
                "package_id": "cny-pack",
                "request_key": str(uuid4()),
                "provider_id": provider["id"],
                "payment_method": "alipay",
            },
            headers=ORIGIN,
        ).status_code
        == 422
    )
    cfg = config("easypay", keys)
    body, headers = signed_event("easypay", cfg, UUID(identity))
    other = client.post("/api/v1/admin/billing/providers", json=data, headers=ORIGIN).json()
    wrong_url = f"/api/v1/billing/providers/{other['id']}/webhook"
    assert client.post(wrong_url, content=body, headers=headers).status_code == 400

    async def concurrent():
        repo = ProviderRepository(app.state.control)
        row = await repo.get(UUID(provider["id"]))
        notice = ProviderGateway(row, repo.decode(row), app.state.settings).notification(
            body, headers
        )
        await asyncio.gather(
            *[app.state.billing.fulfill_provider(row.id, notice) for _ in range(6)]
        )

    client.portal.call(concurrent)
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 100
    assert client.get("/api/v1/billing/entries").json()["total"] == 1
    # A later valid callback must not reuse a transaction already credited to another order.
    next_order = client.post(
        "/api/v1/billing/checkout",
        json={
            "package_id": "cny-pack",
            "request_key": str(uuid4()),
            "provider_id": other["id"],
            "payment_method": "alipay",
        },
        headers=ORIGIN,
    ).json()["order_id"]
    next_body, next_headers = signed_event(
        "easypay", cfg, UUID(next_order), trade_id="second-trade"
    )
    assert client.post(wrong_url, content=next_body, headers=next_headers).status_code == 200
    duplicate_order = client.post(
        "/api/v1/billing/checkout",
        json={
            "package_id": "cny-pack",
            "request_key": str(uuid4()),
            "provider_id": other["id"],
            "payment_method": "alipay",
        },
        headers=ORIGIN,
    ).json()["order_id"]
    duplicate_body, duplicate_headers = signed_event(
        "easypay", cfg, UUID(duplicate_order), trade_id="second-trade"
    )
    assert (
        client.post(wrong_url, content=duplicate_body, headers=duplicate_headers).status_code == 400
    )
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 200
    assert actor["id"]
