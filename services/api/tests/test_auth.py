import asyncio
from email import policy
from email.parser import BytesParser
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from redis.exceptions import ConnectionError

from tooldawn.config import Settings
from tooldawn.integrations.mail import MailSender
from tooldawn.main import create_app
from tooldawn.modules.auth.limiter import AuthLimiter
from tooldawn.modules.auth.schemas import (
    CredentialsInput,
    EmailRequest,
    PasswordInput,
    PasswordLogin,
    ResetPasswordRequest,
    VerifyRequest,
)


@pytest.mark.parametrize("schema", [PasswordInput, CredentialsInput, ResetPasswordRequest])
@pytest.mark.parametrize(
    "password", ["abc123", "abcdef", "123456", "!!!!!!", "中文密码测试", "x" * 128]
)
def test_new_password_policy_accepts_any_composition(schema, password):
    fields = {"new_password": password}
    if schema is not PasswordInput:
        fields["email"] = "test@example.com"
    if schema is ResetPasswordRequest:
        fields.update(challenge_id=uuid4(), code="123456")
    assert schema(**fields).new_password == password


@pytest.mark.parametrize("schema", [PasswordInput, CredentialsInput, ResetPasswordRequest])
@pytest.mark.parametrize("password", ["", "12345", "abcde", "中文密码短", "x" * 129])
def test_new_password_policy_rejects_invalid_length(schema, password):
    fields = {"new_password": password}
    if schema is not PasswordInput:
        fields["email"] = "test@example.com"
    if schema is ResetPasswordRequest:
        fields.update(challenge_id=uuid4(), code="123456")
    with pytest.raises(ValidationError):
        schema(**fields)


def test_login_does_not_apply_new_password_policy_to_existing_credentials():
    assert PasswordLogin(email="test@example.com", password="old").password == "old"


def test_auth_input_normalization_and_ascii_code():
    assert str(EmailRequest(email="  Person@EXAMPLE.COM  ").email) == "person@example.com"
    with pytest.raises(ValidationError):
        VerifyRequest(email="person@example.com", challenge_id=uuid4(), code="１２３４５６")


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"origin": "https://untrusted.example"},
        {
            "origin": "http://localhost:3000",
            "sec-fetch-site": "cross-site",
        },
    ],
)
def test_auth_rejects_untrusted_write_origins(headers):
    app = create_app(Settings(_env_file=None, environment="test", redis_url=None))
    with TestClient(app) as client:
        for path in ("email-code", "verify", "logout", "password-reset/code", "password-reset"):
            response = client.post(f"/api/v1/auth/{path}", headers=headers, json={})
            assert response.status_code == 403
            assert response.headers["cache-control"] == "no-store"


def test_unconfigured_auth_fails_explicitly():
    with TestClient(create_app(Settings(_env_file=None, redis_url=None))) as client:
        response = client.get("/api/v1/me")
        assert response.status_code == 503
        assert response.headers["cache-control"] == "no-store"


def test_login_rate_limit_fails_closed():
    async def run():
        cache = AsyncMock()
        cache.eval.side_effect = ConnectionError("private-redis-details")
        cache.set.side_effect = ConnectionError("private-redis-details")
        limiter = AuthLimiter(cache)
        for call in (limiter.check("send", "ip", 2, 60), limiter.cooldown("a@example.com")):
            with pytest.raises(HTTPException) as error:
                await call
            assert error.value.status_code == 503
            assert "private-redis-details" not in error.value.detail

    asyncio.run(run())


@pytest.mark.parametrize("purpose", ["login", "password_reset"])
def test_development_mail_writes_readable_email_only_to_outbox(tmp_path, purpose):
    settings = Settings(_env_file=None, mail_mode="file", mail_outbox=str(tmp_path))
    challenge_id = str(uuid4())
    asyncio.run(MailSender(settings).send_code("test@example.com", "012345", challenge_id, purpose))
    message = BytesParser(policy=policy.default).parsebytes(
        (tmp_path / f"{challenge_id}.eml").read_bytes()
    )
    assert message["To"] == "test@example.com"
    assert "012345" in message.get_content()
    action = "重置密码" if purpose == "password_reset" else "登录"
    assert action in message["Subject"]
    assert action in message.get_content()
    assert len(list(tmp_path.iterdir())) == 1


def test_production_requires_real_auth_delivery():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            catalog_backend="postgres",
            database_url="postgresql+asyncpg://a:b@localhost/test",
            mail_mode="file",
        )
