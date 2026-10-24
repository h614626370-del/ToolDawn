from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class EmailRequest(BaseModel):
    email: EmailStr = Field(max_length=254)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class VerifyRequest(EmailRequest):
    challenge_id: UUID
    code: str = Field(pattern=r"^[0-9]{6}$")


class ChallengeResponse(BaseModel):
    challenge_id: UUID
    expires_in: int = 600
    resend_after: int = 60


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    email: str
    role: Literal["user", "admin"]
    created_at: datetime
    display_name: str = ""
    is_superadmin: bool = False
    must_change_password: bool = False
    has_password: bool = False


class PasswordLogin(EmailRequest):
    password: str = Field(min_length=1, max_length=128, repr=False)


class ProfileInput(BaseModel):
    model_config = {"extra": "forbid"}
    display_name: str = Field(max_length=60)


class PasswordInput(BaseModel):
    model_config = {"extra": "forbid"}
    current_password: str = Field(default="", max_length=128, repr=False)
    new_password: str = Field(min_length=12, max_length=128, repr=False)


class CredentialsInput(PasswordInput):
    email: EmailStr = Field(max_length=254)
