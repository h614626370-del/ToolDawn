import asyncio
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from tooldawn.config import Settings


class MailSender:
    def __init__(self, settings: Settings, control=None):
        self.settings = settings
        self.control = control

    async def send_code(self, email: str, code: str, challenge_id: str) -> None:
        if self.control:
            sender = MailSender(await self.control.effective())
            return await sender.send_code(email, code, challenge_id)
        message = EmailMessage()
        message["From"] = self.settings.smtp_from
        message["To"] = email
        message["Subject"] = "ToolDawn 登录验证码"
        message.set_content(
            f"你的登录验证码是：{code}\n\n10 分钟内有效，请勿转发。\n如非本人操作，请忽略此邮件。"
        )
        await asyncio.to_thread(self._deliver, message, challenge_id)

    def _deliver(self, message: EmailMessage, challenge_id: str) -> None:
        settings = self.settings
        if settings.mail_mode == "file":
            if settings.environment == "production":
                raise RuntimeError("File mail delivery is development-only")
            directory = Path(settings.mail_outbox)
            directory.mkdir(parents=True, exist_ok=True)
            with os.fdopen(
                os.open(
                    directory / f"{challenge_id}.eml", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                ),
                "wb",
            ) as stream:
                stream.write(message.as_bytes())
            return
        context = ssl.create_default_context()
        if settings.smtp_security == "tls":
            client = smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=15, context=context
            )
        else:
            client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
        with client:
            if settings.smtp_security == "starttls":
                client.starttls(context=context)
            if settings.smtp_username:
                client.login(
                    settings.smtp_username,
                    settings.smtp_password.get_secret_value() if settings.smtp_password else "",
                )
            client.send_message(message)
