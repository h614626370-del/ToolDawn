import asyncio
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from smtplib import SMTPException
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select

from tooldawn.modules.admin.repository import audit
from tooldawn.modules.auth.dependencies import auth_service, check_origin, client_ip
from tooldawn.modules.auth.models import EmailChallenge, SessionRecord, UserRecord
from tooldawn.modules.auth.passwords import hash_password
from tooldawn.modules.auth.schemas import ChallengeResponse, EmailRequest, ResetPasswordRequest
from tooldawn.modules.auth.security import code_digest

router = APIRouter(tags=["auth"], dependencies=[Depends(check_origin)])
INVALID_CODE = "验证码无效或已过期，请重新获取。"


def reset_digest(secret, challenge_id, user, code):
    # Bind codes to both the account and its current password. Changing the password
    # invalidates every outstanding reset code without locking other challenges.
    context = f"password_reset:{user.id}:{user.password_hash or ''}:{user.email}"
    return code_digest(secret, str(challenge_id), context, code)


@router.post("/auth/password-reset/code", response_model=ChallengeResponse)
async def send_reset_code(data: EmailRequest, request: Request):
    service = auth_service(request)
    email = str(data.email)
    await service.limiter.check("send", client_ip(request), 20, 3600)
    await service.limiter.check("email", email, 10, 3600)
    await service.limiter.cooldown(email)
    identity = uuid4()
    async with service.repository.sessions() as db:
        user = await db.scalar(select(UserRecord).where(UserRecord.email == email))
    # Preserve the existing rule that superadmins cannot authenticate via email codes.
    # Always return the same response shape, including for nonexistent accounts.
    if user is None or user.disabled or user.is_superadmin:
        return ChallengeResponse(challenge_id=identity)
    code = f"{secrets.randbelow(1_000_000):06d}"
    await service.repository.save_challenge(
        EmailChallenge(
            id=identity,
            email=email,
            purpose="password_reset",
            code_digest=reset_digest(
                service.settings.auth_secret.get_secret_value(), identity, user, code
            ),
            attempts=0,
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
            consumed=False,
        )
    )
    try:
        await service.mail.send_code(email, code, str(identity), purpose="password_reset")
    except (OSError, RuntimeError, SMTPException):
        await service.repository.remove_challenge(identity)
        # A delivery failure must not disclose whether this address has an account.
    return ChallengeResponse(challenge_id=identity)


@router.post("/auth/password-reset", status_code=204)
async def reset_password(data: ResetPasswordRequest, request: Request):
    service = auth_service(request)
    await service.limiter.check("verify", client_ip(request), 60, 600)
    await service.limiter.check("reset-email", str(data.email), 10, 600)
    encoded = await asyncio.to_thread(hash_password, data.new_password)
    valid = False
    async with service.repository.sessions.begin() as db:
        challenge = await db.scalar(
            select(EmailChallenge).where(EmailChallenge.id == data.challenge_id).with_for_update()
        )
        if (
            challenge is not None
            and challenge.purpose == "password_reset"
            and challenge.email == str(data.email)
            and not challenge.consumed
            and challenge.expires_at > datetime.now(UTC)
            and challenge.attempts < 5
        ):
            challenge.attempts += 1
            user = await db.scalar(
                select(UserRecord).where(UserRecord.email == str(data.email)).with_for_update()
            )
            if user is not None and not user.disabled and not user.is_superadmin:
                digest = reset_digest(
                    service.settings.auth_secret.get_secret_value(), challenge.id, user, data.code
                )
                if hmac.compare_digest(challenge.code_digest, digest):
                    challenge.consumed = True
                    user.password_hash = encoded
                    user.must_change_password = False
                    await db.execute(delete(SessionRecord).where(SessionRecord.user_id == user.id))
                    audit(
                        db,
                        user.id,
                        "auth.password_reset",
                        str(user.id),
                        ["password_hash", "sessions"],
                    )
                    valid = True
    # Commit failed attempts too, and never create accounts or sessions here.
    if not valid:
        raise HTTPException(400, INVALID_CODE)
