import asyncio
import hashlib
import hmac
import json
import os
import time
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from test_admin_postgres import ORIGIN, admin_client, login  # noqa: F401

from tooldawn.config import Settings
from tooldawn.modules.auth.models import UserRecord
from tooldawn.modules.billing.gateway import StripeGateway
from tooldawn.modules.billing.models import CreditRecord, OrderRecord, WalletRecord
from tooldawn.modules.billing.schemas import AdjustmentInput, CreditPackage

PACKAGE = CreditPackage(id="test-pack", credits=100, unit_amount=500, currency="usd")
WEBHOOK_SECRET = "whsec_test_only_never_a_real_key"
pytestmark = pytest.mark.skipif(
    not os.environ.get("TOOLDAWN_TEST_DATABASE_URL"), reason="Requires migrated test PostgreSQL"
)


@pytest.fixture
def billing_client(admin_client):  # noqa: F811
    client, service, prefix = admin_client
    app = client.app
    app.state.settings.credit_packages = [PACKAGE]
    app.state.gateway = StripeGateway(
        Settings(
            _env_file=None,
            environment="test",
            stripe_secret_key="sk_test_placeholder",
            stripe_webhook_secret=WEBHOOK_SECRET,
        )
    )

    async def checkout(order):
        return f"cs_test_{order.id}", f"https://checkout.stripe.com/c/pay/{order.id}"

    app.state.gateway.checkout = AsyncMock(side_effect=checkout)
    try:
        yield client, service, prefix
    finally:

        async def cleanup():
            async with service.repository.sessions.begin() as db:
                users = select(UserRecord.id).where(UserRecord.email.startswith(prefix))
                for model in (CreditRecord, WalletRecord, OrderRecord):
                    await db.execute(delete(model).where(model.user_id.in_(users)))

        client.portal.call(cleanup)


def new_order(client, request_key=None):
    return client.post(
        "/api/v1/billing/checkout",
        json={
            "package_id": PACKAGE.id,
            "request_key": request_key or str(uuid4()),
        },
        headers=ORIGIN,
    )


def notification(client, order_id, event_type="checkout.session.completed", **changes):
    payload = {
        "id": f"cs_test_{order_id}",
        "mode": "payment",
        "metadata": {"order_id": order_id, "credits": "999999999"},
        "client_reference_id": order_id,
        "currency": "usd",
        "amount_total": 500,
        "payment_status": "paid",
        **changes,
    }
    body = json.dumps(
        {
            "id": "evt_test_" + uuid4().hex,
            "object": "event",
            "livemode": False,
            "type": event_type,
            "data": {"object": payload},
        }
    ).encode()
    stamp = int(time.time())
    signature = hmac.new(
        WEBHOOK_SECRET.encode(), str(stamp).encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    return client.post(
        "/api/v1/billing/webhook",
        content=body,
        headers={
            "stripe-signature": f"t={stamp},v1={signature}",
            "content-type": "application/json",
        },
    )


def test_billing_guards_disabled_provider_and_privacy(billing_client):
    client, service, prefix = billing_client
    for path in ("wallet", "orders", "entries"):
        response = client.get(f"/api/v1/billing/{path}")
        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"
    user = login(client, service, prefix + "@example.com")
    assert client.get("/api/v1/admin/billing/orders").status_code == 403
    assert (
        client.post(
            f"/api/v1/admin/users/{user['id']}/credits",
            json={
                "amount": 10,
                "reason": "test",
                "request_key": str(uuid4()),
            },
            headers=ORIGIN,
        ).status_code
        == 403
    )
    assert new_order(client).status_code == 200
    response = client.post(
        "/api/v1/billing/checkout",
        json={
            "package_id": PACKAGE.id,
            "request_key": str(uuid4()),
        },
    )
    assert response.status_code == 403
    client.app.state.gateway = StripeGateway(Settings(_env_file=None))
    assert new_order(client).status_code == 503
    assert client.get("/api/v1/billing/packages").json()["enabled"] is False
    assert "secret" not in client.get("/api/v1/billing/packages").text


def test_checkout_snapshot_idempotency_and_owner_isolation(billing_client):
    client, service, prefix = billing_client
    login(client, service, prefix + "@example.com")
    key = str(uuid4())
    result = new_order(client, key)
    assert result.status_code == 200
    assert new_order(client, key).json() == result.json()
    assert client.app.state.gateway.checkout.await_count == 1
    order_id = result.json()["order_id"]
    assert client.get(f"/api/v1/billing/orders/{order_id}").json()["credits"] == 100
    assert (
        client.post(
            "/api/v1/billing/checkout",
            json={
                "package_id": PACKAGE.id,
                "request_key": str(uuid4()),
                "unit_amount": 1,
            },
            headers=ORIGIN,
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/billing/checkout",
            json={
                "package_id": "other",
                "request_key": key,
            },
            headers=ORIGIN,
        ).status_code
        == 409
    )
    login(client, service, prefix + "-other@example.com")
    assert client.get(f"/api/v1/billing/orders/{order_id}").status_code == 404
    assert client.get("/api/v1/billing/orders").json()["items"] == []


def test_signed_payment_exactly_once_and_late_event(billing_client):
    client, service, prefix = billing_client
    login(client, service, prefix + "@example.com")
    order_id = new_order(client).json()["order_id"]
    assert notification(client, order_id, payment_status="unpaid").status_code == 200
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 0
    for event in (
        "checkout.session.async_payment_succeeded",
        "checkout.session.completed",
        "checkout.session.expired",
        "checkout.session.async_payment_failed",
    ):
        assert notification(client, order_id, event).status_code == 200
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 100
    ledger = client.get("/api/v1/billing/entries").json()
    assert ledger["total"] == 1
    assert ledger["items"][0]["balance_after"] == 100
    assert client.get(f"/api/v1/billing/orders/{order_id}").json()["status"] == "paid"


def test_concurrent_callbacks_credit_once(billing_client):
    client, service, prefix = billing_client
    login(client, service, prefix + "@example.com")
    order_id = new_order(client).json()["order_id"]
    payload = {
        "id": f"cs_test_{order_id}",
        "mode": "payment",
        "metadata": {"order_id": order_id},
        "client_reference_id": order_id,
        "currency": "usd",
        "amount_total": 500,
        "payment_status": "paid",
    }

    async def race():
        await asyncio.gather(
            *[
                client.app.state.billing.fulfill(payload, "checkout.session.completed")
                for _ in range(8)
            ]
        )

    client.portal.call(race)
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 100
    assert client.get("/api/v1/billing/entries").json()["total"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"amount_total": 1},
        {"currency": "eur"},
        {"id": "cs_test_wrong"},
        {"client_reference_id": str(uuid4())},
        {"mode": "subscription"},
    ],
)
def test_payment_mismatch_never_credits(billing_client, changes):
    client, service, prefix = billing_client
    login(client, service, prefix + "@example.com")
    order_id = new_order(client).json()["order_id"]
    assert notification(client, order_id, **changes).status_code == 400
    assert client.get("/api/v1/billing/wallet").json()["balance"] == 0
    assert client.get("/api/v1/billing/entries").json()["total"] == 0


def test_invalid_webhooks_and_pending_limit(billing_client):
    client, service, prefix = billing_client
    assert client.post("/api/v1/billing/webhook", content=b"{}").status_code == 400
    assert client.post("/api/v1/billing/webhook", content=b"x" * 262145).status_code == 413
    login(client, service, prefix + "@example.com")
    for _ in range(5):
        assert new_order(client).status_code == 200
    assert new_order(client).status_code == 429


def test_admin_credit_adjustments_atomic_and_concurrent(billing_client):
    client, service, prefix = billing_client
    target = login(client, service, prefix + "-member@example.com")
    actor = login(client, service, prefix + "-admin@example.com", admin=True)
    url = f"/api/v1/admin/users/{target['id']}/credits"
    data = {"amount": 100, "reason": "support credit", "request_key": str(uuid4())}
    result = client.post(url, json=data, headers=ORIGIN)
    assert result.status_code == 200
    assert client.post(url, json=data, headers=ORIGIN).json() == result.json()
    assert client.post(url, json={**data, "amount": 200}, headers=ORIGIN).status_code == 409
    assert (
        client.post(
            url,
            json={
                **data,
                "amount": -101,
                "request_key": str(uuid4()),
            },
            headers=ORIGIN,
        ).status_code
        == 409
    )

    async def race():
        repo = client.app.state.billing
        adjustments = [
            AdjustmentInput(amount=-30, reason="concurrency test", request_key=uuid4())
            for _ in range(4)
        ]
        return await asyncio.gather(
            *[repo.adjust(UUID(target["id"]), value, UUID(actor["id"])) for value in adjustments],
            return_exceptions=True,
        )

    outcomes = client.portal.call(race)
    assert sum(isinstance(value, Exception) for value in outcomes) == 1
    assert client.get(f"/api/v1/admin/users/{target['id']}/wallet").json()["balance"] == 10
    assert client.get(url).json()["total"] == 4
    assert client.get(url, params={"offset": 3, "limit": 1}).json()["total"] == 4
    assert client.get("/api/v1/admin/billing/orders").status_code == 200
