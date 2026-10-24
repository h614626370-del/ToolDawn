import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from test_admin_postgres import ORIGIN, admin_client, login  # noqa: F401
from test_billing_postgres import billing_client  # noqa: F401
from test_operations_postgres import ops, settings_input, sign_in  # noqa: F401

from tooldawn.modules.admin.models import AuditRecord
from tooldawn.modules.auth.models import UserRecord
from tooldawn.modules.billing.models import OrderRecord

pytestmark = pytest.mark.skipif(
    not os.environ.get("TOOLDAWN_TEST_DATABASE_URL"), reason="Requires migrated test PostgreSQL"
)


def test_payment_filters_currency_totals_and_date_boundaries(billing_client):  # noqa: F811
    client, service, prefix = billing_client
    for path in ("orders", "statistics", "config"):
        assert client.get(f"/api/v1/admin/billing/{path}").status_code == 401
    user = login(client, service, prefix + "@example.com")
    for path in ("orders", "statistics", "config"):
        assert client.get(f"/api/v1/admin/billing/{path}").status_code == 403
    begin = datetime(2026, 1, 1, tzinfo=UTC)
    ids = [uuid4() for _ in range(5)]

    async def seed():
        async with service.repository.sessions.begin() as db:
            for index, (status, currency) in enumerate(
                [
                    ("paid", "usd"),
                    ("paid", "eur"),
                    ("pending", "usd"),
                    ("failed", "usd"),
                    ("paid", "usd"),
                ]
            ):
                db.add(
                    OrderRecord(
                        id=ids[index],
                        user_id=UUID(user["id"]),
                        request_key=uuid4(),
                        package_id="test-package",
                        credits=100,
                        unit_amount=500,
                        currency=currency,
                        status=status,
                        created_at=begin + timedelta(days=index),
                        expires_at=begin + timedelta(days=index, hours=1),
                        paid_at=begin + timedelta(days=index) if status == "paid" else None,
                    )
                )

    client.portal.call(seed)
    login(client, service, prefix + "-admin@example.com", admin=True)
    assert client.get("/api/v1/admin/billing/config").status_code == 403
    params = {
        "q": prefix + "@example.com",
        "start": begin.isoformat(),
        "end": (begin + timedelta(days=4)).isoformat(),
    }
    stats = client.get("/api/v1/admin/billing/statistics", params=params)
    assert stats.status_code == 200, stats.text
    assert stats.json() == {
        "total": 4,
        "statuses": {
            "paid": 2,
            "pending": 1,
            "failed": 1,
            "expired": 0,
        },
        "revenue": [
            {"currency": "eur", "amount": 500, "credits": 100, "orders": 1},
            {"currency": "usd", "amount": 500, "credits": 100, "orders": 1},
        ],
    }
    url = "/api/v1/admin/billing/orders"
    result = client.get(url, params={**params, "status": "paid", "limit": 1}).json()
    assert result["total"] == 2 and len(result["items"]) == 1
    assert client.get(url, params={"q": str(ids[0])}).json()["total"] == 1
    assert client.get(url, params={**params, "q": "test-package"}).json()["total"] == 4
    assert client.get(url, params={"q": "%"}).json()["total"] == 0
    assert client.get(url, params={"status": "invalid"}).status_code == 422
    for path in ("orders", "statistics"):
        endpoint = f"/api/v1/admin/billing/{path}"
        assert client.get(endpoint, params={"start": "2026-01-01"}).status_code == 422
        assert (
            client.get(
                endpoint, params={"start": begin.isoformat(), "end": begin.isoformat()}
            ).status_code
            == 422
        )
    login(client, service, prefix + "-other@example.com")
    assert client.get("/api/v1/billing/orders").json()["total"] == 0


def test_payment_config_scoped_save_secrets_and_revision(ops):  # noqa: F811
    client, app, prefix, _ = ops
    url = "/api/v1/admin/billing/config"
    body = {"revision": 0, "credit_packages": []}
    assert client.put(url, json=body, headers=ORIGIN).status_code == 401
    sign_in(client, prefix, "user")
    assert client.put(url, json=body, headers=ORIGIN).status_code == 403
    actor = sign_in(client, prefix)
    full = settings_input(client, site_name="Keep this site", smtp_password="test-mail-secret")
    assert client.put("/api/v1/admin/settings", json=full, headers=ORIGIN).status_code == 200
    before = client.get(url).json()
    assert set(before) == {
        "revision",
        "credit_packages",
        "stripe_secret_key_set",
        "stripe_webhook_secret_set",
    }
    body = {
        "revision": before["revision"],
        "credit_packages": [
            {"id": "pack", "credits": 100, "unit_amount": 500, "currency": "usd"},
        ],
        "stripe_secret_key": "sk_test_example",
        "stripe_webhook_secret": "whsec_example",
    }
    assert client.put(url, json=body).status_code == 403
    assert client.put(url, json={**body, "site_name": "bad"}, headers=ORIGIN).status_code == 422
    response = client.put(url, json=body, headers=ORIGIN)
    assert response.status_code == 200, response.text
    assert response.json()["stripe_secret_key_set"]
    assert "sk_test_example" not in response.text
    current = client.portal.call(app.state.control.current)
    assert current.site_name == "Keep this site"
    assert current.smtp_password.get_secret_value() == "test-mail-secret"
    assert client.put(url, json=body, headers=ORIGIN).status_code == 409
    # Null keeps credentials; clear removes both without exposing either.
    body.update(
        revision=response.json()["revision"], stripe_secret_key=None, stripe_webhook_secret=None
    )
    kept = client.put(url, json=body, headers=ORIGIN).json()
    assert kept["stripe_secret_key_set"] and kept["stripe_webhook_secret_set"]
    duplicate = {
        **body,
        "revision": kept["revision"],
        "credit_packages": body["credit_packages"] * 2,
    }
    assert client.put(url, json=duplicate, headers=ORIGIN).status_code == 422
    body.update(revision=kept["revision"], stripe_secret_key="", stripe_webhook_secret="")
    cleared = client.put(url, json=body, headers=ORIGIN).json()
    assert not cleared["stripe_secret_key_set"] and not cleared["stripe_webhook_secret_set"]

    async def demote():
        async with app.state.control.sessions.begin() as db:
            user = await db.get(UserRecord, UUID(actor["id"]))
            user.is_superadmin = False

    client.portal.call(demote)
    assert client.get(url).status_code == 403
    assert client.put(url, json=body, headers=ORIGIN).status_code == 403


def test_user_filters_and_audit_actor_target_dates(ops):  # noqa: F811
    client, app, prefix, _ = ops
    for path in ("users", "audit"):
        assert client.get(f"/api/v1/admin/{path}").status_code == 401
    sign_in(client, prefix, "user")
    for path in ("users", "audit"):
        assert client.get(f"/api/v1/admin/{path}").status_code == 403
    actor = sign_in(client, prefix)
    begin = datetime(2026, 1, 1, tzinfo=UTC)

    async def seed():
        async with app.state.control.sessions.begin() as db:
            db.add(
                AuditRecord(
                    id=uuid4(),
                    actor_id=UUID(actor["id"]),
                    action="payments.update",
                    target=prefix + "-target",
                    changed_fields=["credit_packages"],
                    created_at=begin,
                )
            )

    client.portal.call(seed)
    users = client.get(
        "/api/v1/admin/users", params={"q": prefix, "role": "user", "disabled": False}
    )
    assert users.status_code == 200 and users.json()["total"] == 2
    assert (
        client.get("/api/v1/admin/users", params={"q": prefix, "disabled": True}).json()["total"]
        == 0
    )
    for keyword in (prefix + "-admin@example.com", prefix + "-target"):
        result = client.get(
            "/api/v1/admin/audit",
            params={
                "q": keyword,
                "start": begin.isoformat(),
                "end": (begin + timedelta(days=1)).isoformat(),
            },
        )
        assert result.status_code == 200 and result.json()["total"] == 1
    assert (
        client.get("/api/v1/admin/audit", params={"q": prefix, "end": begin.isoformat()}).json()[
            "total"
        ]
        == 0
    )
    assert client.get("/api/v1/admin/audit", params={"start": "2026-01-01"}).status_code == 422
