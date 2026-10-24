from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from tooldawn.modules.billing.schemas import CreditPackage


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TOOLDAWN_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["development", "test", "production"] = "development"
    catalog_backend: Literal["seed", "postgres"] = "seed"
    database_url: str | None = Field(default=None, repr=False)
    redis_url: str | None = Field(default=None, repr=False)
    auth_secret: SecretStr | None = None
    public_origins: list[str] = ["http://127.0.0.1:3000", "http://localhost:3000"]
    session_days: int = Field(default=30, ge=1, le=90)
    mail_mode: Literal["file", "smtp"] = "file"
    mail_outbox: str = "../../.runtime/mail"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str = "ToolDawn <noreply@tooldawn.local>"
    smtp_security: Literal["starttls", "tls"] = "starttls"
    stripe_secret_key: SecretStr | None = None
    stripe_webhook_secret: SecretStr | None = None
    billing_origin: str = "http://127.0.0.1:3000"
    credit_packages: list[CreditPackage] = []
    llm_base_url: str | None = Field(default=None, repr=False)
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    ai_tool_cost: int = Field(default=1, ge=0, le=1000)
    bootstrap_admin: bool = True
    bootstrap_credentials: str = "../../.runtime/initial-admin.json"
    encryption_key: SecretStr | None = None

    @model_validator(mode="after")
    def validate_backend(self) -> "Settings":
        if any((self.llm_base_url, self.llm_api_key, self.llm_model)):
            if not all((self.llm_base_url, self.llm_api_key, self.llm_model)):
                raise ValueError("LLM requires base URL, API key and model")
            url = urlsplit(self.llm_base_url)
            local = (
                self.environment != "production"
                and url.hostname in {"localhost", "127.0.0.1", "::1"}
                and url.scheme == "http"
            )
            if (
                (url.scheme != "https" and not local)
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
            ):
                raise ValueError("LLM base URL must use HTTPS without credentials or query strings")
        if len({p.id for p in self.credit_packages}) != len(self.credit_packages):
            raise ValueError("Credit package IDs must be unique")
        if self.stripe_secret_key or self.stripe_webhook_secret:
            if not (self.stripe_secret_key and self.stripe_webhook_secret):
                raise ValueError("Stripe requires both API and webhook secrets")
            if self.billing_origin not in self.public_origins:
                raise ValueError("Billing origin must be an allowed public origin")
            if (
                self.environment != "production"
                and not self.stripe_secret_key.get_secret_value().startswith("sk_test_")
            ):
                raise ValueError("Non-production billing requires a Stripe test key")
        if self.environment == "production" and self.catalog_backend != "postgres":
            raise ValueError("Production requires the postgres catalog backend")
        if self.catalog_backend == "postgres" and not self.database_url:
            raise ValueError("The postgres catalog backend requires TOOLDAWN_DATABASE_URL")
        if self.database_url and not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("Use a postgresql+asyncpg database URL")
        if self.redis_url and not self.redis_url.startswith(("redis://", "rediss://")):
            raise ValueError("Use a redis or rediss URL")
        if self.auth_secret and len(self.auth_secret.get_secret_value()) < 32:
            raise ValueError("Auth secret must contain at least 32 characters")
        if self.mail_mode == "smtp" and not self.smtp_host:
            raise ValueError("SMTP mode requires a host")
        if self.environment == "production":
            if not self.auth_secret or not self.redis_url:
                raise ValueError("Production requires auth secret and Redis")
            if not self.public_origins or any(
                not origin.startswith("https://") for origin in self.public_origins
            ):
                raise ValueError("Production public origins must use HTTPS")
        return self
