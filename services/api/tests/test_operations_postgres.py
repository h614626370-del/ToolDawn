import json
import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from tooldawn.config import Settings
from tooldawn.main import create_app
from tooldawn.modules.admin.models import AuditRecord
from tooldawn.modules.auth.bootstrap import bootstrap_admin
from tooldawn.modules.auth.models import EmailChallenge, UserRecord
from tooldawn.modules.auth.passwords import hash_password
from tooldawn.modules.operations.models import ModelAccount, SettingRecord, TicketRecord

pytestmark = pytest.mark.skipif(
    not os.environ.get("TOOLDAWN_TEST_DATABASE_URL"), reason="Requires migrated test PostgreSQL"
)
ORIGIN = {"origin": "http://localhost:3000"}
PASSWORD = "test-password-for-operations"


@pytest.fixture
def ops(tmp_path):
    settings = Settings(
        _env_file=None,
        environment="test",
        catalog_backend="postgres",
        database_url=os.environ["TOOLDAWN_TEST_DATABASE_URL"],
        redis_url=os.environ.get("TOOLDAWN_TEST_REDIS_URL", "redis://localhost:6379"),
        auth_secret="test-only-secret-" * 4,
        bootstrap_credentials=str(tmp_path / "initial-admin.json"),
    )
    app = create_app(settings)
    prefix = f"ops-{uuid4().hex}"
    with TestClient(app) as client:
        app.state.auth.limiter = AsyncMock()
        app.state.auth.mail = AsyncMock()

        async def setup():
            async with app.state.control.sessions.begin() as db:
                saved = [
                    (row.key, row.value, row.revision, row.updated_at)
                    for row in await db.scalars(select(SettingRecord))
                ]
                await db.execute(delete(SettingRecord))
                for name, admin in (("admin", True), ("user", False), ("other", False)):
                    db.add(
                        UserRecord(
                            id=uuid4(),
                            email=f"{prefix}-{name}@example.com",
                            role="admin" if admin else "user",
                            display_name=name,
                            password_hash=hash_password(PASSWORD),
                            is_superadmin=admin,
                            must_change_password=False,
                            disabled=False,
                            created_at=datetime.now(UTC),
                        )
                    )
                return saved

        saved = client.portal.call(setup)
        try:
            yield client, app, prefix, settings
        finally:

            async def cleanup():
                async with app.state.control.sessions.begin() as db:
                    users = select(UserRecord.id).where(UserRecord.email.startswith(prefix))
                    await db.execute(delete(TicketRecord).where(TicketRecord.user_id.in_(users)))
                    await db.execute(delete(AuditRecord).where(AuditRecord.actor_id.in_(users)))
                    await db.execute(
                        delete(EmailChallenge).where(EmailChallenge.email.startswith(prefix))
                    )
                    await db.execute(delete(UserRecord).where(UserRecord.email.startswith(prefix)))
                    await db.execute(
                        delete(ModelAccount).where(ModelAccount.name.startswith(prefix))
                    )
                    await db.execute(delete(SettingRecord))
                    for key, value, revision, updated_at in saved:
                        db.add(
                            SettingRecord(
                                key=key, value=value, revision=revision, updated_at=updated_at
                            )
                        )

            client.portal.call(cleanup)


def sign_in(client, prefix, role="admin", password=PASSWORD):
    result = client.post(
        "/api/v1/auth/password",
        headers=ORIGIN,
        json={"email": f"{prefix}-{role}@example.com", "password": password},
    )
    assert result.status_code == 200, result.text
    return result.json()


def settings_input(client, **updates):
    config = client.get("/api/v1/admin/settings").json()
    return {**{key: value for key, value in config.items() if not key.endswith("_set")}, **updates}


def test_settings_secrets_permissions_and_live_effects(ops):
    client, app, prefix, _ = ops
    assert client.get("/api/v1/site").status_code == 200
    assert client.get("/api/v1/admin/settings").status_code == 401
    sign_in(client, prefix, "user")
    assert client.get("/api/v1/admin/settings").status_code == 403
    sign_in(client, prefix)
    payload = settings_input(
        client,
        site_name="Changed site",
        smtp_password="private-smtp-key",
        ai_tool_cost=7,
        ai_enabled=False,
    )
    result = client.put("/api/v1/admin/settings", headers=ORIGIN, json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["smtp_password_set"]
    assert "private-smtp-key" not in result.text
    assert client.put("/api/v1/admin/settings", headers=ORIGIN, json=payload).status_code == 409
    public = client.get("/api/v1/site").json()
    assert public["site_name"] == "Changed site"
    assert "smtp_password" not in public

    async def stored():
        async with app.state.control.sessions() as db:
            return (await db.get(SettingRecord, "runtime")).value

    assert "private-smtp-key" not in json.dumps(client.portal.call(stored))
    config = client.portal.call(app.state.control.current)
    assert config.ai_tool_cost == 7 and not config.ai_enabled
    assert config.smtp_password.get_secret_value() == "private-smtp-key"
    keep = settings_input(client, smtp_password=None)
    assert client.put("/api/v1/admin/settings", headers=ORIGIN, json=keep).json()[
        "smtp_password_set"
    ]
    clear = settings_input(client, smtp_password="")
    assert not client.put("/api/v1/admin/settings", headers=ORIGIN, json=clear).json()[
        "smtp_password_set"
    ]


def test_model_accounts_encryption_revision_and_routing(ops):
    client, app, prefix, _ = ops
    sign_in(client, prefix)
    payload = {
        "name": prefix,
        "base_url": "https://example.com/v1",
        "model": "test-model",
        "api_key": "private-model-key",
    }
    result = client.post("/api/v1/admin/model-accounts", headers=ORIGIN, json=payload)
    assert result.status_code == 200, result.text
    account = result.json()
    assert account["key_set"] and "private-model-key" not in result.text
    save = client.put(
        "/api/v1/admin/settings",
        headers=ORIGIN,
        json=settings_input(client, default_account_id=account["id"]),
    )
    assert save.status_code == 200, save.text
    identity, resolved = client.portal.call(app.state.accounts.resolve, "ai-rewriter")
    assert str(identity) == account["id"]
    assert resolved.llm_api_key.get_secret_value() == "private-model-key"
    update = {**payload, "api_key": None, "enabled": False, "revision": account["revision"]}
    path = "/api/v1/admin/model-accounts/" + account["id"]
    assert client.put(path, headers=ORIGIN, json=update).status_code == 200
    assert client.put(path, headers=ORIGIN, json=update).status_code == 409
    assert client.portal.call(app.state.accounts.resolve, "ai-rewriter")[1] is None
    sign_in(client, prefix, "user")
    assert client.get("/api/v1/admin/model-accounts").status_code == 403


def test_ticket_owner_isolation_idempotency_and_staff_reply(ops):
    client, _, prefix, _ = ops
    sign_in(client, prefix, "user")
    data = {"subject": "Test ticket", "body": "Please help", "request_key": str(uuid4())}
    result = client.post("/api/v1/tickets", json=data, headers=ORIGIN)
    assert result.status_code == 200, result.text
    ticket = result.json()
    path = "/api/v1/tickets/" + ticket["id"]
    assert client.post("/api/v1/tickets", json=data, headers=ORIGIN).json()["id"] == ticket["id"]
    sign_in(client, prefix, "other")
    assert client.get(path).status_code == 404
    assert client.get("/api/v1/tickets").json()["total"] == 0
    sign_in(client, prefix)
    reply = {"body": "Resolved", "revision": 1, "request_key": str(uuid4()), "status": "replied"}
    admin_path = "/api/v1/admin/tickets/" + ticket["id"]
    response = client.post(admin_path + "/replies", json=reply, headers=ORIGIN)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "replied"
    assert (
        len(client.post(admin_path + "/replies", json=reply, headers=ORIGIN).json()["messages"])
        == 2
    )
    sign_in(client, prefix, "user")
    assert client.get(path).json()["messages"][1]["staff"]
    assert (
        client.patch(path, json={"status": "closed", "revision": 1}, headers=ORIGIN).status_code
        == 409
    )
    assert (
        client.patch(path, json={"status": "closed", "revision": 2}, headers=ORIGIN).status_code
        == 200
    )


def test_initial_password_gate_rotation_and_sessions(ops):
    client, app, prefix, _ = ops
    actor = sign_in(client, prefix)

    async def force_change():
        async with app.state.control.sessions.begin() as db:
            row = await db.get(UserRecord, UUID(actor["id"]))
            row.must_change_password = True

    client.portal.call(force_change)
    assert client.get("/api/v1/admin/dashboard").status_code == 403
    result = client.put(
        "/api/v1/me/admin-credentials",
        headers=ORIGIN,
        json={
            "email": f"{prefix}-admin@example.com",
            "current_password": PASSWORD,
            "new_password": "changed-test-password-123",
        },
    )
    assert result.status_code == 200, result.text
    assert not result.json()["must_change_password"]
    assert client.get("/api/v1/admin/dashboard?days=30").status_code == 200
    assert len(client.get("/api/v1/me/sessions").json()) == 1
    client.cookies.clear()
    assert (
        client.post(
            "/api/v1/auth/password",
            headers=ORIGIN,
            json={
                "email": f"{prefix}-admin@example.com",
                "password": PASSWORD,
            },
        ).status_code
        == 400
    )
    sign_in(client, prefix, password="changed-test-password-123")


def test_dashboard_monitor_and_usage_filters(ops):
    client, _, prefix, _ = ops
    sign_in(client, prefix)
    data = client.get("/api/v1/admin/dashboard?days=7")
    assert data.status_code == 200, data.text
    assert len(data.json()["daily"]) == 7
    assert client.get("/api/v1/admin/dashboard?days=2").status_code == 422
    monitor = client.get("/api/v1/admin/monitoring")
    assert monitor.status_code == 200, monitor.text
    assert monitor.json()["database"]["ok"]
    assert (
        client.get("/api/v1/admin/usage?start=2026-10-24&end=2026-10-25T00:00:00Z").status_code
        == 422
    )
    assert client.get("/api/v1/admin/audit").status_code == 200
    sign_in(client, prefix, "user")
    assert client.get("/api/v1/me/usage").json()["total"] == 0


def test_bootstrap_runs_only_once(ops):
    client, app, prefix, settings = ops
    # Existing superadmin suppresses generation, and the marker prevents recreation.
    development = settings.model_copy(update={"environment": "development"})
    client.portal.call(bootstrap_admin, app.state.control.sessions, development)

    async def demote():
        async with app.state.control.sessions.begin() as db:
            row = await db.scalar(
                select(UserRecord).where(UserRecord.email == f"{prefix}-admin@example.com")
            )
            row.is_superadmin = False

    client.portal.call(demote)
    client.portal.call(bootstrap_admin, app.state.control.sessions, development)
    from pathlib import Path

    assert not Path(settings.bootstrap_credentials).exists()


def test_bootstrap_generates_private_credentials_and_allows_first_login(ops):
    from pathlib import Path

    client, app, prefix, settings = ops

    async def demote():
        async with app.state.control.sessions.begin() as db:
            row = await db.scalar(
                select(UserRecord).where(UserRecord.email == f"{prefix}-admin@example.com")
            )
            row.is_superadmin = False

    client.portal.call(demote)
    development = settings.model_copy(update={"environment": "development"})
    client.portal.call(bootstrap_admin, app.state.control.sessions, development)
    path = Path(settings.bootstrap_credentials)
    credentials = json.loads(path.read_text())
    try:
        result = client.post("/api/v1/auth/password", headers=ORIGIN, json=credentials)
        assert result.status_code == 200
        assert result.json()["is_superadmin"] and result.json()["must_change_password"]
        assert client.get("/api/v1/admin/settings").status_code == 403
        client.portal.call(bootstrap_admin, app.state.control.sessions, development)
        assert json.loads(path.read_text()) == credentials
        changed = client.put(
            "/api/v1/me/admin-credentials",
            headers=ORIGIN,
            json={
                "email": f"{prefix}-generated@example.com",
                "current_password": credentials["password"],
                "new_password": PASSWORD,
            },
        )
        assert changed.status_code == 200
        assert not path.exists()
        assert client.get("/api/v1/admin/settings").status_code == 200
    finally:

        async def cleanup_generated():
            async with app.state.control.sessions.begin() as db:
                identity = await db.scalar(
                    select(UserRecord.id).where(UserRecord.email == credentials["email"])
                )
                if identity:
                    await db.execute(delete(AuditRecord).where(AuditRecord.actor_id == identity))
                    await db.execute(delete(UserRecord).where(UserRecord.id == identity))

        client.portal.call(cleanup_generated)
