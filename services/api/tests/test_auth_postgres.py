import asyncio
import os
from datetime import UTC, datetime, timedelta
from typing import Annotated
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from tooldawn.config import Settings
from tooldawn.main import create_app
from tooldawn.modules.auth.dependencies import require_admin
from tooldawn.modules.auth.models import EmailChallenge, SessionRecord, UserRecord
from tooldawn.modules.auth.schemas import UserResponse, VerifyRequest
from tooldawn.modules.auth.security import token_digest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TOOLDAWN_TEST_DATABASE_URL"), reason="Requires migrated test PostgreSQL"
)
ORIGIN = {"origin": "http://localhost:3000"}


@pytest.fixture
def auth_client():
    settings = Settings(
        _env_file=None,
        environment="test",
        catalog_backend="postgres",
        database_url=os.environ["TOOLDAWN_TEST_DATABASE_URL"],
        redis_url="redis://localhost:6379",
        auth_secret="test-only-secret-" * 4,
    )
    app = create_app(settings)

    @app.get("/test/admin")
    async def admin(user: Annotated[UserResponse, Depends(require_admin)]):
        return {"role": user.role}

    with TestClient(app) as client:
        service = app.state.auth
        service.limiter = AsyncMock()
        service.mail = AsyncMock()
        email = f"auth-test-{uuid4().hex}@example.com"
        try:
            yield client, service, email
        finally:

            async def cleanup():
                async with service.repository.sessions.begin() as db:
                    await db.execute(delete(EmailChallenge).where(EmailChallenge.email == email))
                    await db.execute(delete(UserRecord).where(UserRecord.email == email))

            client.portal.call(cleanup)


def challenge(client, service, email):
    response = client.post("/api/v1/auth/email-code", json={"email": email}, headers=ORIGIN)
    assert response.status_code == 200
    code = service.mail.send_code.call_args.args[1]
    assert code not in response.text
    return {"email": email, "challenge_id": response.json()["challenge_id"], "code": code}


def login(client, data):
    return client.post("/api/v1/auth/verify", json=data, headers=ORIGIN)


def test_login_replay_logout_and_admin_permissions(auth_client):
    client, service, email = auth_client
    assert client.get("/api/v1/me").status_code == 401
    data = challenge(client, service, email)
    response = login(client, data)
    assert response.status_code == 200
    assert response.json()["role"] == "user"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/api/v1" in cookie
    assert response.headers["cache-control"] == "no-store"
    token = client.cookies.get("tooldawn_session")
    assert client.get("/api/v1/me").json()["email"] == email
    assert login(client, data).status_code == 400
    assert (
        client.get("/test/admin", headers={"cookie": f"tooldawn_session={token}"}).status_code
        == 403
    )
    client.portal.call(service.repository.create_admin, email)
    client.portal.call(service.repository.create_admin, email)
    assert client.get("/api/v1/me").json()["role"] == "admin"
    assert (
        client.get("/test/admin", headers={"cookie": f"tooldawn_session={token}"}).status_code
        == 200
    )
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204
    assert (
        client.get("/api/v1/me", headers={"cookie": f"tooldawn_session={token}"}).status_code == 401
    )


def test_failed_attempts_commit_and_lock_after_five(auth_client):
    client, service, email = auth_client
    data = challenge(client, service, email)
    wrong = "000000" if data["code"] != "000000" else "999999"
    for _ in range(5):
        assert login(client, {**data, "code": wrong}).status_code == 400
    assert login(client, data).status_code == 400

    async def attempts():
        async with service.repository.sessions() as db:
            return await db.scalar(
                select(EmailChallenge.attempts).where(
                    EmailChallenge.id == UUID(data["challenge_id"])
                )
            )

    assert client.portal.call(attempts) == 5


@pytest.mark.parametrize("condition", ["expired-code", "disabled-user", "expired-session"])
def test_expiration_and_disabled_user(auth_client, condition):
    client, service, email = auth_client
    data = challenge(client, service, email)
    if condition == "expired-code":

        async def expire_code():
            async with service.repository.sessions.begin() as db:
                await db.execute(
                    update(EmailChallenge)
                    .where(EmailChallenge.id == UUID(data["challenge_id"]))
                    .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
                )

        client.portal.call(expire_code)
        assert login(client, data).status_code == 400
        return
    assert login(client, data).status_code == 200

    async def invalidate():
        async with service.repository.sessions.begin() as db:
            if condition == "disabled-user":
                await db.execute(
                    update(UserRecord).where(UserRecord.email == email).values(disabled=True)
                )
            else:
                await db.execute(
                    update(SessionRecord)
                    .where(
                        SessionRecord.token_digest
                        == token_digest(client.cookies.get("tooldawn_session"))
                    )
                    .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
                )

    client.portal.call(invalidate)
    assert client.get("/api/v1/me").status_code == 401
    if condition == "disabled-user":
        assert login(client, challenge(client, service, email)).status_code == 400


def test_simultaneous_verify_is_single_use(auth_client):
    client, service, email = auth_client
    data = VerifyRequest(**challenge(client, service, email))

    async def verify_twice():
        return await asyncio.gather(
            service.verify(data, "test-ip"),
            service.verify(data, "test-ip"),
            return_exceptions=True,
        )

    results = client.portal.call(verify_twice)
    assert sum(isinstance(result, tuple) for result in results) == 1
    assert sum(getattr(result, "status_code", None) == 400 for result in results) == 1


def test_new_login_revokes_previous_session(auth_client):
    client, service, email = auth_client
    assert login(client, challenge(client, service, email)).status_code == 200
    old_token = client.cookies.get("tooldawn_session")
    assert login(client, challenge(client, service, email)).status_code == 200
    assert client.get("/api/v1/me").status_code == 200
    assert (
        client.get(
            "/api/v1/me",
            headers={
                "cookie": f"tooldawn_session={old_token}",
            },
        ).status_code
        == 401
    )


def test_delivery_failure_removes_challenge(auth_client):
    client, service, email = auth_client
    service.mail.send_code.side_effect = OSError("private-smtp-details")
    response = client.post("/api/v1/auth/email-code", json={"email": email}, headers=ORIGIN)
    assert response.status_code == 503
    assert "private-smtp-details" not in response.text

    async def remaining():
        async with service.repository.sessions() as db:
            return await db.scalar(select(EmailChallenge.id).where(EmailChallenge.email == email))

    assert client.portal.call(remaining) is None


def reset_code(client, service, email):
    response = client.post(
        "/api/v1/auth/password-reset/code", json={"email": email}, headers=ORIGIN
    )
    assert response.status_code == 200
    assert service.mail.send_code.call_args.kwargs == {"purpose": "password_reset"}
    return {
        "email": email,
        "challenge_id": response.json()["challenge_id"],
        "code": service.mail.send_code.call_args.args[1],
        "new_password": "new-password-123456",
    }


def test_password_reset_isolated_single_use_and_revokes_all_sessions(auth_client):
    client, service, email = auth_client
    assert login(client, challenge(client, service, email)).status_code == 200
    old_token = client.cookies.get("tooldawn_session")
    client.cookies.clear()
    assert login(client, challenge(client, service, email)).status_code == 200
    other_token = client.cookies.get("tooldawn_session")
    login_code = challenge(client, service, email)
    assert (
        client.post(
            "/api/v1/auth/password-reset",
            headers=ORIGIN,
            json={**login_code, "new_password": "new-password-123456"},
        ).status_code
        == 400
    )
    data = reset_code(client, service, email)
    assert (
        login(client, {key: data[key] for key in ("email", "challenge_id", "code")}).status_code
        == 400
    )
    older = reset_code(client, service, email)
    assert client.post("/api/v1/auth/password-reset", headers=ORIGIN, json=data).status_code == 204
    for token in (old_token, other_token):
        assert (
            client.get("/api/v1/me", headers={"cookie": f"tooldawn_session={token}"}).status_code
            == 401
        )
    for stale in (data, older):
        assert (
            client.post("/api/v1/auth/password-reset", headers=ORIGIN, json=stale).status_code
            == 400
        )
    assert (
        client.post(
            "/api/v1/auth/password",
            headers=ORIGIN,
            json={"email": email, "password": data["new_password"]},
        ).status_code
        == 200
    )


def test_password_reset_attempt_limit_is_persisted(auth_client):
    client, service, email = auth_client
    assert login(client, challenge(client, service, email)).status_code == 200
    data = reset_code(client, service, email)
    wrong = "000000" if data["code"] != "000000" else "999999"
    for _ in range(5):
        assert (
            client.post(
                "/api/v1/auth/password-reset", headers=ORIGIN, json={**data, "code": wrong}
            ).status_code
            == 400
        )
    assert client.post("/api/v1/auth/password-reset", headers=ORIGIN, json=data).status_code == 400


def test_concurrent_reset_only_one_password_wins(auth_client):
    from types import SimpleNamespace

    from fastapi import Request

    from tooldawn.modules.auth.recovery import reset_password
    from tooldawn.modules.auth.schemas import ResetPasswordRequest

    client, service, email = auth_client
    assert login(client, challenge(client, service, email)).status_code == 200
    first = ResetPasswordRequest(**reset_code(client, service, email))
    second = ResetPasswordRequest(**reset_code(client, service, email))
    second.new_password = "another-password-123456"
    request = Request(
        {
            "type": "http",
            "app": SimpleNamespace(state=SimpleNamespace(auth=service)),
            "client": ("test-ip", 1),
            "headers": [],
        }
    )

    async def reset_twice():
        return await asyncio.gather(
            reset_password(first, request), reset_password(second, request), return_exceptions=True
        )

    results = client.portal.call(reset_twice)
    assert sum(result is None for result in results) == 1
    assert sum(getattr(result, "status_code", None) == 400 for result in results) == 1
