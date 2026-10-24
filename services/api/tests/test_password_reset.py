from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tooldawn.config import Settings
from tooldawn.main import create_app
from tooldawn.modules.auth.models import EmailChallenge, UserRecord
from tooldawn.modules.auth.recovery import reset_digest

ORIGIN = {"origin": "http://localhost:3000"}
SECRET = "test-only-secret-" * 4


@pytest.fixture
def recovery():
    settings = Settings(_env_file=None, environment="test", redis_url=None, auth_secret=SECRET)
    app = create_app(settings)
    with TestClient(app) as client:
        db = AsyncMock()
        db.add = MagicMock()
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=db)
        context.__aexit__ = AsyncMock(return_value=False)
        sessions = MagicMock(return_value=context)
        sessions.begin.return_value = context
        service = SimpleNamespace(
            settings=settings,
            repository=SimpleNamespace(
                sessions=sessions, save_challenge=AsyncMock(), remove_challenge=AsyncMock()
            ),
            limiter=AsyncMock(),
            mail=AsyncMock(),
        )
        app.state.auth = service
        yield client, service, db


def account(**overrides):
    values = dict(
        id=uuid4(),
        email="person@example.com",
        password_hash="old-hash",
        disabled=False,
        is_superadmin=False,
        role="user",
        must_change_password=False,
    )
    return UserRecord(**(values | overrides))


def reset_challenge(user, **overrides):
    identity = uuid4()
    values = dict(
        id=identity,
        email=user.email,
        purpose="password_reset",
        attempts=0,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        consumed=False,
        code_digest=reset_digest(SECRET, identity, user, "123456"),
    )
    return EmailChallenge(**(values | overrides))


def payload(challenge):
    return dict(
        email=challenge.email,
        challenge_id=str(challenge.id),
        code="123456",
        new_password="a-new-password-123",
    )


@pytest.mark.parametrize("kind", ["missing", "disabled", "superadmin", "user", "admin"])
def test_send_does_not_disclose_account_status(recovery, kind):
    client, service, db = recovery
    db.scalar.return_value = (
        None
        if kind == "missing"
        else account(
            disabled=kind == "disabled",
            is_superadmin=kind == "superadmin",
            role="admin" if kind == "admin" else "user",
        )
    )
    response = client.post(
        "/api/v1/auth/password-reset/code", json={"email": "Person@Example.com"}, headers=ORIGIN
    )
    assert response.status_code == 200
    assert set(response.json()) == {"challenge_id", "expires_in", "resend_after"}
    assert "no-store" in response.headers["cache-control"]
    assert service.mail.send_code.await_count == (1 if kind in ("user", "admin") else 0)
    service.limiter.cooldown.assert_awaited_once_with("person@example.com")
    if kind in ("user", "admin"):
        assert service.repository.save_challenge.call_args.args[0].purpose == "password_reset"
        assert service.mail.send_code.call_args.kwargs == {"purpose": "password_reset"}


def test_delivery_failure_invalidates_code_without_disclosing_account(recovery):
    client, service, db = recovery
    db.scalar.return_value = account()
    service.mail.send_code.side_effect = OSError("private-smtp-details")
    response = client.post(
        "/api/v1/auth/password-reset/code", json={"email": "person@example.com"}, headers=ORIGIN
    )
    assert response.status_code == 200
    service.repository.remove_challenge.assert_awaited_once()
    assert "private-smtp-details" not in response.text


@pytest.mark.parametrize(
    "kind",
    [
        "expired",
        "consumed",
        "locked",
        "login",
        "wrong-code",
        "wrong-email",
        "disabled",
        "superadmin",
        "missing-user",
        "changed-password",
    ],
)
def test_invalid_reset_cannot_modify_password_or_sessions(recovery, kind):
    client, service, db = recovery
    user = account(disabled=kind == "disabled", is_superadmin=kind == "superadmin")
    challenge = reset_challenge(user)
    data = payload(challenge)
    if kind == "expired":
        challenge.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    elif kind == "consumed":
        challenge.consumed = True
    elif kind == "locked":
        challenge.attempts = 5
    elif kind == "login":
        challenge.purpose = "login"
    elif kind == "wrong-code":
        data["code"] = "000000"
    elif kind == "wrong-email":
        data["email"] = "someone-else@example.com"
    elif kind == "changed-password":
        user.password_hash = "changed-hash"
    before = user.password_hash
    db.scalar.side_effect = [challenge, None if kind == "missing-user" else user]
    response = client.post("/api/v1/auth/password-reset", json=data, headers=ORIGIN)
    assert response.status_code == 400
    assert user.password_hash == before
    db.execute.assert_not_awaited()
    if kind == "wrong-code":
        assert challenge.attempts == 1
        service.repository.sessions.begin.return_value.__aexit__.assert_awaited_once_with(
            None, None, None
        )


@pytest.mark.parametrize("role", ["user", "admin"])
def test_reset_changes_password_revokes_sessions_and_audits(recovery, role):
    from tooldawn.modules.auth.passwords import verify_password

    client, service, db = recovery
    user = account(role=role)
    challenge = reset_challenge(user)
    db.scalar.side_effect = [challenge, user]
    response = client.post("/api/v1/auth/password-reset", json=payload(challenge), headers=ORIGIN)
    assert response.status_code == 204
    assert "set-cookie" not in response.headers
    assert challenge.consumed
    assert verify_password("a-new-password-123", user.password_hash)
    assert "DELETE FROM sessions" in str(db.execute.call_args.args[0])
    assert db.add.call_args.args[0].action == "auth.password_reset"


@pytest.mark.parametrize("password", ["short", "x" * 129])
def test_reset_rejects_invalid_password_length(recovery, password):
    client, service, db = recovery
    data = payload(reset_challenge(account())) | {"new_password": password}
    assert client.post("/api/v1/auth/password-reset", json=data, headers=ORIGIN).status_code == 422
    db.scalar.assert_not_awaited()
