from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    TypeAdapter,
    field_validator,
    model_validator,
)

from tooldawn.modules.ai_tools.registry import TOOLS
from tooldawn.modules.billing.schemas import CreditPackage


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolOverride(StrictInput):
    account_id: UUID | None = None
    cost: int | None = Field(default=None, ge=0, le=1000)
    enabled: bool = True
    instruction: str = Field(default="", max_length=8000)


class RuntimeConfig(StrictInput):
    site_name: str = Field(default="ToolDawn", min_length=1, max_length=60)
    announcement: str = Field(default="", max_length=500)
    contact_email: str = Field(default="", max_length=254)
    registration_enabled: bool = True
    ai_enabled: bool = True
    tickets_enabled: bool = True
    ai_tool_cost: int = Field(default=1, ge=0, le=1000)
    ai_requests_per_minute: int = Field(default=10, ge=1, le=100)
    default_account_id: UUID | None = None
    tool_overrides: dict[str, ToolOverride] = Field(default_factory=dict)
    mail_mode: Literal["file", "smtp"] = "file"
    smtp_host: str | None = Field(default=None, max_length=254)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = Field(default=None, max_length=254)
    smtp_from: str = Field(default="ToolDawn <noreply@tooldawn.local>", max_length=254)
    smtp_security: Literal["starttls", "tls"] = "starttls"
    credit_packages: list[CreditPackage] = Field(default_factory=list, max_length=20)
    # Null preserves a stored secret; empty string explicitly removes it.
    smtp_password: SecretStr | None = None
    stripe_secret_key: SecretStr | None = None
    stripe_webhook_secret: SecretStr | None = None

    @field_validator("contact_email")
    @classmethod
    def validate_contact(cls, value):
        return str(TypeAdapter(EmailStr).validate_python(value)) if value else ""

    @model_validator(mode="after")
    def validate_values(self):
        if any(slug not in TOOLS for slug in self.tool_overrides):
            raise ValueError("Unknown internal tool")
        if len({p.id for p in self.credit_packages}) != len(self.credit_packages):
            raise ValueError("Package IDs must be unique")
        if self.mail_mode == "smtp" and not self.smtp_host:
            raise ValueError("SMTP requires a host")
        for value in (self.smtp_host, self.smtp_from, self.smtp_username):
            if value and ("\n" in value or "\r" in value):
                raise ValueError("Invalid email configuration")
        return self


class ConfigInput(RuntimeConfig):
    revision: int = Field(ge=0)


class AccountInput(StrictInput):
    name: str = Field(min_length=1, max_length=80)
    base_url: str = Field(min_length=8, max_length=500)
    api_key: SecretStr | None = None
    model: str = Field(min_length=1, max_length=120)
    enabled: bool = True
    revision: int = Field(default=0, ge=0)

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, value):
        url = urlsplit(value)
        if (
            url.scheme not in {"https", "http"}
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or (url.scheme == "http" and url.hostname not in {"127.0.0.1", "localhost", "::1"})
        ):
            raise ValueError("Base URL must use HTTPS without credentials or query strings")
        return value.rstrip("/")


class TicketInput(StrictInput):
    subject: str = Field(min_length=2, max_length=120)
    category: Literal["general", "billing", "tool", "account"] = "general"
    body: str = Field(min_length=2, max_length=5000)
    request_key: UUID

    @field_validator("subject", "body")
    @classmethod
    def nonempty(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("Content must not be blank")
        return value.strip()


class ReplyInput(StrictInput):
    body: str = Field(min_length=1, max_length=5000)
    revision: int = Field(ge=1)
    status: Literal["open", "processing", "replied", "closed"] | None = None
    request_key: UUID

    @field_validator("body")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Content must not be blank")
        return value.strip()


class TicketState(StrictInput):
    status: Literal["open", "processing", "replied", "closed"]
    revision: int = Field(ge=1)
