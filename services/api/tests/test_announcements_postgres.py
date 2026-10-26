import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from tooldawn.config import Settings
from tooldawn.main import create_app
from tooldawn.modules.admin.models import AuditRecord
from tooldawn.modules.announcements.models import Announcement
from tooldawn.modules.auth.models import SessionRecord, UserRecord
from tooldawn.modules.auth.security import token_digest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TOOLDAWN_TEST_DATABASE_URL"),
    reason="Requires migrated test PostgreSQL",
)
ORIGIN = {"origin": "http://localhost:3000"}


@pytest.fixture
def announcements():
    settings = Settings(
        _env_file=None,
        environment="test",
        catalog_backend="postgres",
        database_url=os.environ["TOOLDAWN_TEST_DATABASE_URL"],
        redis_url=os.environ.get("TOOLDAWN_TEST_REDIS_URL", "redis://localhost:6379"),
        auth_secret="test-announcements-secret-" * 3,
        bootstrap_admin=False,
    )
    app = create_app(settings)
    prefix = f"ann-{uuid4().hex}"
    tokens = {role: uuid4().hex for role in ("user", "other", "admin", "super", "initial")}
    with TestClient(app) as client:

        async def setup():
            async with app.state.announcements.sessions.begin() as db:
                for role, token in tokens.items():
                    identity = uuid4()
                    db.add(
                        UserRecord(
                            id=identity,
                            email=f"{prefix}-{role}@example.com",
                            role="user" if role in ("user", "other") else "admin",
                            is_superadmin=role == "super",
                            must_change_password=role == "initial",
                            disabled=False,
                            created_at=datetime.now(UTC),
                        )
                    )
                    await db.flush()
                    db.add(
                        SessionRecord(
                            token_digest=token_digest(token),
                            user_id=identity,
                            created_at=datetime.now(UTC),
                            expires_at=datetime.now(UTC) + timedelta(days=1),
                        )
                    )

        client.portal.call(setup)

        def login(role):
            client.cookies.clear()
            if role:
                client.cookies.set("tooldawn_session", tokens[role])

        try:
            yield client, app, prefix, login
        finally:

            async def cleanup():
                async with app.state.announcements.sessions.begin() as db:
                    users = select(UserRecord.id).where(UserRecord.email.startswith(prefix))
                    await db.execute(delete(Announcement).where(Announcement.created_by.in_(users)))
                    await db.execute(delete(AuditRecord).where(AuditRecord.actor_id.in_(users)))
                    await db.execute(delete(UserRecord).where(UserRecord.email.startswith(prefix)))

            client.portal.call(cleanup)


def create(client, prefix, **values):
    result = client.post(
        "/api/v1/admin/announcements",
        headers=ORIGIN,
        json={
            "title": prefix,
            "content": "## Update\n\nNew tools are ready.",
            **values,
        },
    )
    assert result.status_code == 201, result.text
    return result.json()


def payload(row, **changes):
    keys = (
        "title",
        "content",
        "status",
        "notify_mode",
        "audience",
        "starts_at",
        "ends_at",
        "revision",
    )
    return {key: row[key] for key in keys} | changes


def test_permissions_origin_and_validation(announcements):
    client, _, prefix, login = announcements
    for role, expected in ((None, 401), ("user", 403), ("initial", 403)):
        login(role)
        assert client.get("/api/v1/admin/announcements").status_code == expected
        assert (
            client.post(
                "/api/v1/admin/announcements",
                headers=ORIGIN,
                json={"title": prefix, "content": "body"},
            ).status_code
            == expected
        )
        assert (
            client.put(
                f"/api/v1/admin/announcements/{uuid4()}",
                headers=ORIGIN,
                json={"title": prefix, "content": "body"},
            ).status_code
            == expected
        )
    for role in ("admin", "super"):
        login(role)
        assert client.get("/api/v1/admin/announcements").status_code == 200
        row = create(client, prefix)
        assert (
            client.put(
                f"/api/v1/admin/announcements/{row['id']}",
                headers=ORIGIN,
                json=payload(row, status="archived"),
            ).status_code
            == 200
        )
    assert (
        client.post(
            "/api/v1/admin/announcements",
            json={
                "title": prefix,
                "content": "body",
            },
        ).status_code
        == 403
    )
    for changes in (
        {"title": "  "},
        {"content": " "},
        {"audience": "unknown"},
        {"starts_at": "2026-01-01T00:00:00"},
        {"starts_at": "2026-01-02T00:00:00Z", "ends_at": "2026-01-01T00:00:00Z"},
    ):
        assert (
            client.post(
                "/api/v1/admin/announcements",
                headers=ORIGIN,
                json={
                    "title": prefix,
                    "content": "body",
                    **changes,
                },
            ).status_code
            == 422
        )


def test_visibility_schedule_and_pagination(announcements):
    client, _, prefix, login = announcements
    login("admin")
    now = datetime.now(UTC)
    create(client, prefix)
    create(client, prefix, status="archived")
    create(client, prefix, status="active", starts_at=(now + timedelta(hours=1)).isoformat())
    create(client, prefix, status="active", ends_at=(now - timedelta(seconds=1)).isoformat())
    public = create(client, prefix, status="active", notify_mode="popup")
    members = create(client, prefix, status="active", audience="members")
    login(None)
    result = client.get("/api/v1/announcements").json()
    own = [item for item in result["items"] if item["title"] == prefix]
    assert [item["id"] for item in own] == [public["id"]]
    assert any(item["id"] == public["id"] for item in result["popups"])
    assert client.get("/api/v1/announcements").headers["cache-control"] == "private, no-store"
    login("user")
    own = [
        item["id"]
        for item in client.get("/api/v1/announcements").json()["items"]
        if item["title"] == prefix
    ]
    assert set(own) == {public["id"], members["id"]}
    assert client.get("/api/v1/announcements?limit=1").json()["total"] >= 2
    assert len(client.get("/api/v1/announcements?limit=1").json()["items"]) == 1
    assert client.get("/api/v1/announcements?limit=101").status_code == 422
    login("admin")
    page = client.get(
        "/api/v1/admin/announcements", params={"q": prefix, "status": "active"}
    ).json()
    assert page["total"] == 4


def test_read_isolation_revision_and_archive(announcements):
    client, app, prefix, login = announcements
    login("admin")
    row = create(client, prefix, status="active", notify_mode="popup")
    path = f"/api/v1/admin/announcements/{row['id']}"
    receipt = {"items": [{"id": row["id"], "revision": row["revision"]}]}
    login(None)
    assert (
        client.post("/api/v1/announcements/read", headers=ORIGIN, json=receipt).status_code == 401
    )
    login("user")
    assert client.post("/api/v1/announcements/read", json=receipt).status_code == 403
    assert (
        client.post("/api/v1/announcements/read", headers=ORIGIN, json=receipt).status_code == 204
    )
    assert (
        client.post("/api/v1/announcements/read", headers=ORIGIN, json=receipt).status_code == 204
    )
    page = client.get("/api/v1/announcements").json()
    assert next(item for item in page["items"] if item["id"] == row["id"])["read_at"]
    assert not any(item["id"] == row["id"] for item in page["popups"])
    login("other")
    assert not next(
        item
        for item in client.get("/api/v1/announcements").json()["items"]
        if item["id"] == row["id"]
    )["read_at"]
    login("admin")
    assert (
        client.get("/api/v1/admin/announcements", params={"q": prefix}).json()["items"][0][
            "read_count"
        ]
        == 1
    )
    updated = client.put(path, headers=ORIGIN, json=payload(row, content="Changed")).json()
    assert updated["revision"] == 2
    assert client.put(path, headers=ORIGIN, json=payload(row)).status_code == 409
    # Saving without changes must not reset receipts a second time.
    assert client.put(path, headers=ORIGIN, json=payload(updated)).json()["revision"] == 2
    assert (
        client.get("/api/v1/admin/announcements", params={"q": prefix}).json()["items"][0][
            "read_count"
        ]
        == 0
    )
    login("user")
    assert any(
        item["id"] == row["id"] for item in client.get("/api/v1/announcements").json()["popups"]
    )
    assert (
        client.post("/api/v1/announcements/read", headers=ORIGIN, json=receipt).status_code == 409
    )
    login("admin")
    assert (
        client.put(path, headers=ORIGIN, json=payload(updated, status="archived")).status_code
        == 200
    )
    login("user")
    assert (
        client.post("/api/v1/announcements/read", headers=ORIGIN, json=receipt).status_code == 404
    )
    assert not any(
        item["id"] == row["id"] for item in client.get("/api/v1/announcements").json()["items"]
    )

    async def audit_actions():
        async with app.state.announcements.sessions() as db:
            return list(
                await db.scalars(select(AuditRecord.action).where(AuditRecord.target == row["id"]))
            )

    assert client.portal.call(audit_actions) == [
        "announcement.create",
        "announcement.update",
        "announcement.update",
    ]
