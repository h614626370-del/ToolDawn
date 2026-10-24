import os
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from tooldawn.config import Settings
from tooldawn.main import create_app
from tooldawn.modules.admin.models import AuditRecord
from tooldawn.modules.auth.models import EmailChallenge, UserRecord
from tooldawn.modules.catalog.models import CategoryRecord, ToolRecord

pytestmark = pytest.mark.skipif(
    not os.environ.get("TOOLDAWN_TEST_DATABASE_URL"), reason="Requires migrated test PostgreSQL"
)
ORIGIN = {"origin": "http://localhost:3000"}


@pytest.fixture
def admin_client():
    app = create_app(
        Settings(
            _env_file=None,
            environment="test",
            catalog_backend="postgres",
            database_url=os.environ["TOOLDAWN_TEST_DATABASE_URL"],
            redis_url="redis://localhost:6379",
            auth_secret="test-only-secret-" * 4,
        )
    )
    prefix = f"admin-test-{uuid4().hex}"
    with TestClient(app) as client:
        service = app.state.auth
        service.limiter = AsyncMock()
        service.mail = AsyncMock()
        try:
            yield client, service, prefix
        finally:

            async def cleanup():
                async with service.repository.sessions.begin() as db:
                    users = select(UserRecord.id).where(UserRecord.email.startswith(prefix))
                    await db.execute(delete(AuditRecord).where(AuditRecord.actor_id.in_(users)))
                    await db.execute(delete(ToolRecord).where(ToolRecord.slug.startswith(prefix)))
                    await db.execute(
                        delete(CategoryRecord).where(CategoryRecord.slug.startswith(prefix))
                    )
                    await db.execute(
                        delete(EmailChallenge).where(EmailChallenge.email.startswith(prefix))
                    )
                    await db.execute(delete(UserRecord).where(UserRecord.email.startswith(prefix)))

            client.portal.call(cleanup)


def challenge(client, service, email):
    response = client.post("/api/v1/auth/email-code", json={"email": email}, headers=ORIGIN)
    assert response.status_code == 200
    return {
        "email": email,
        "challenge_id": response.json()["challenge_id"],
        "code": service.mail.send_code.call_args.args[1],
    }


def login(client, service, email, admin=False):
    if admin:
        client.portal.call(service.repository.create_admin, email)
    response = client.post(
        "/api/v1/auth/verify", json=challenge(client, service, email), headers=ORIGIN
    )
    assert response.status_code == 200
    return response.json()


def category_data(prefix):
    return {"slug": prefix, "name": prefix, "icon": "grid", "color": "green", "sort_order": 123}


def tool_data(prefix):
    return {
        "slug": prefix,
        "name": prefix,
        "summary": "Test summary",
        "description": "Test description",
        "category": prefix,
        "kind": "external",
        "status": "available",
        "external_url": "https://example.com/",
        "published": False,
        "keywords": ["test"],
        "features": ["Test feature"],
    }


def post(client, resource, data):
    return client.post(f"/api/v1/admin/{resource}", json=data, headers=ORIGIN)


def test_admin_authorization_origin_and_private_responses(admin_client):
    client, service, prefix = admin_client
    operations = [
        ("GET", "/categories", None),
        ("GET", "/tools", None),
        ("GET", "/users", None),
        ("POST", "/categories", category_data(prefix)),
        ("PUT", f"/categories/{prefix}", category_data(prefix)),
        ("POST", "/tools", tool_data(prefix)),
        ("PUT", f"/tools/{prefix}", tool_data(prefix)),
        ("PATCH", f"/users/{uuid4()}", {"disabled": True}),
    ]
    for expected in (401, 403):
        for method, path, data in operations:
            response = client.request(method, "/api/v1/admin" + path, json=data, headers=ORIGIN)
            assert response.status_code == expected
            assert response.headers["cache-control"] == "no-store"
        login(client, service, prefix + "@example.com")
    client.portal.call(service.repository.create_admin, prefix + "@example.com")
    response = client.post(
        "/api/v1/admin/categories",
        json=category_data(prefix),
        headers={"origin": "https://untrusted.example"},
    )
    assert response.status_code == 403
    for resource in ("categories", "tools", "users"):
        response = client.get(f"/api/v1/admin/{resource}")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"


def test_catalog_publication_revision_and_atomic_audit(admin_client):
    client, service, prefix = admin_client
    actor = login(client, service, prefix + "@example.com", admin=True)
    category = category_data(prefix)
    assert post(client, "categories", category).status_code == 201
    assert post(client, "categories", category).status_code == 409
    updated = client.put(
        f"/api/v1/admin/categories/{prefix}",
        json={**category, "name": "Updated", "revision": 1},
        headers=ORIGIN,
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert (
        client.put(f"/api/v1/admin/categories/{prefix}", json=category, headers=ORIGIN).status_code
        == 409
    )
    tool = tool_data(prefix)
    response = post(client, "tools", tool)
    assert response.status_code == 201
    assert post(client, "tools", tool).status_code == 409
    assert client.get(f"/api/v1/tools/{prefix}").status_code == 404
    assert client.get("/api/v1/tools", params={"q": prefix}).json()["total"] == 0
    counts = {c["slug"]: c["tool_count"] for c in client.get("/api/v1/categories").json()}
    assert counts[prefix] == 0
    counts = {c["slug"]: c["tool_count"] for c in client.get("/api/v1/admin/categories").json()}
    assert counts[prefix] == 1
    published = {**tool, "published": True, "revision": 1, "featured": True}
    response = client.put(f"/api/v1/admin/tools/{prefix}", json=published, headers=ORIGIN)
    assert response.status_code == 200
    assert response.json()["revision"] == 2
    assert client.get(f"/api/v1/tools/{prefix}").status_code == 200
    assert client.get("/api/v1/tools", params={"category": prefix}).json()["total"] == 1
    assert (
        client.put(f"/api/v1/admin/tools/{prefix}", json=published, headers=ORIGIN).status_code
        == 409
    )
    response = client.get(
        "/api/v1/admin/tools", params={"q": prefix, "published": True, "limit": 1}
    )
    assert response.json()["total"] == 1
    assert len(response.json()["items"]) == 1
    assert client.get("/api/v1/admin/tools", params={"q": prefix, "offset": 1}).json() == {
        "items": [],
        "total": 1,
    }
    assert (
        client.get("/api/v1/admin/tools", params={"category": prefix, "q": "%"}).json()["total"]
        == 0
    )
    assert (
        client.put(
            f"/api/v1/admin/tools/{prefix}",
            json={**tool, "revision": 2},
            headers=ORIGIN,
        ).status_code
        == 200
    )
    assert client.get(f"/api/v1/tools/{prefix}").status_code == 404

    async def audits():
        async with service.repository.sessions() as db:
            return (
                await db.scalars(
                    select(AuditRecord).where(AuditRecord.actor_id == UUID(actor["id"]))
                )
            ).all()

    logs = client.portal.call(audits)
    assert sorted(log.action for log in logs) == [
        "category.create",
        "category.update",
        "tool.create",
        "tool.update",
        "tool.update",
    ]
    assert all(isinstance(field, str) for log in logs for field in log.changed_fields)


def test_admin_validation_and_missing_records(admin_client):
    client, service, prefix = admin_client
    login(client, service, prefix + "@example.com", admin=True)
    assert post(client, "categories", category_data(prefix)).status_code == 201
    tool = tool_data(prefix)
    for patch in (
        {"category": "missing-" + prefix},
        {"external_url": "http://example.com"},
        {"external_url": "https://user:secret@example.com"},
        {"kind": "internal", "external_url": None},
        {"role": "admin"},
        {"image": "/images/../../secret.png"},
        {"slug": "../bad"},
    ):
        assert post(client, "tools", {**tool, **patch}).status_code == 422
    assert (
        client.put("/api/v1/admin/tools/different-slug", json=tool, headers=ORIGIN).status_code
        == 422
    )
    assert client.put(f"/api/v1/admin/tools/{prefix}", json=tool, headers=ORIGIN).status_code == 404
    assert (
        client.patch(
            f"/api/v1/admin/users/{uuid4()}", json={"disabled": True}, headers=ORIGIN
        ).status_code
        == 404
    )
    assert client.get("/api/v1/admin/tools", params={"limit": 101}).status_code == 422


def test_disable_revokes_sessions_and_challenges_restore_requires_login(admin_client):
    client, service, prefix = admin_client
    email = prefix + "-user@example.com"
    user = login(client, service, email)
    old_token = client.cookies.get("tooldawn_session")
    pending = challenge(client, service, email)
    client.cookies.clear()
    actor = login(client, service, prefix + "-admin@example.com", admin=True)
    for disabled in (True, False):
        response = client.patch(
            f"/api/v1/admin/users/{user['id']}", json={"disabled": disabled}, headers=ORIGIN
        )
        assert response.status_code == 200
        assert response.json()["disabled"] is disabled
        assert (
            client.get(
                "/api/v1/me", headers={"cookie": f"tooldawn_session={old_token}"}
            ).status_code
            == 401
        )
    assert client.post("/api/v1/auth/verify", json=pending, headers=ORIGIN).status_code == 400
    assert (
        client.patch(
            f"/api/v1/admin/users/{actor['id']}", json={"disabled": True}, headers=ORIGIN
        ).status_code
        == 409
    )
    response = client.get("/api/v1/admin/users", params={"q": email})
    assert response.json()["total"] == 1
    assert set(response.json()["items"][0]) == {"id", "email", "role", "disabled", "created_at"}
    client.cookies.clear()
    assert login(client, service, email)["id"] == user["id"]
