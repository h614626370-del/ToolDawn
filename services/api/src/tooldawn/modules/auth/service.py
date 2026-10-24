import secrets
from datetime import UTC, datetime, timedelta
from smtplib import SMTPException
from uuid import uuid4

from fastapi import HTTPException

from tooldawn.config import Settings
from tooldawn.integrations.mail import MailSender
from tooldawn.modules.auth.limiter import AuthLimiter
from tooldawn.modules.auth.models import EmailChallenge
from tooldawn.modules.auth.repository import AuthRepository
from tooldawn.modules.auth.schemas import ChallengeResponse, VerifyRequest
from tooldawn.modules.auth.security import code_digest, token_digest


class AuthService:
    def __init__(
        self, repository: AuthRepository, limiter: AuthLimiter, mail: MailSender, settings: Settings
    ):
        self.repository = repository
        self.limiter = limiter
        self.mail = mail
        self.settings = settings

    async def send_code(self, email: str, client_ip: str) -> ChallengeResponse:
        await self.limiter.check("send", client_ip, 20, 3600)
        await self.limiter.check("email", email, 10, 3600)
        await self.limiter.cooldown(email)
        challenge_id = uuid4()
        code = f"{secrets.randbelow(1_000_000):06d}"
        digest = code_digest(
            self.settings.auth_secret.get_secret_value(), str(challenge_id), email, code
        )
        await self.repository.save_challenge(
            EmailChallenge(
                id=challenge_id,
                email=email,
                code_digest=digest,
                attempts=0,
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
                consumed=False,
            )
        )
        try:
            await self.mail.send_code(email, code, str(challenge_id))
        except (OSError, RuntimeError, SMTPException):
            await self.repository.remove_challenge(challenge_id)
            raise HTTPException(503, "邮件暂时无法发送，请稍后重试。") from None
        return ChallengeResponse(challenge_id=challenge_id)

    async def verify(self, data: VerifyRequest, client_ip: str):
        await self.limiter.check("verify", client_ip, 60, 600)
        token = secrets.token_urlsafe(32)
        digest = code_digest(
            self.settings.auth_secret.get_secret_value(),
            str(data.challenge_id),
            str(data.email),
            data.code,
        )
        allow_create = True
        control = getattr(self, "control", None)
        if control:
            allow_create = (await control.current()).registration_enabled
        user = await self.repository.verify(
            data.challenge_id,
            str(data.email),
            digest,
            token_digest(token),
            self.settings.session_days,
            allow_create,
        )
        if user is None:
            raise HTTPException(400, "验证码无效或已过期，请重新获取。")
        return user, token
