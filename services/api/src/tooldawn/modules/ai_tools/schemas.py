from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_key: UUID
    text: str = Field(min_length=2, max_length=12000)
    context: str = Field(default="", max_length=1000)
    style: str = Field(max_length=20)
    language: Literal["zh", "en", "ja", "ko", "fr", "de", "es"] = "zh"

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if len(value.strip()) < 2:
            raise ValueError("Text must contain at least two non-whitespace characters")
        return value.strip()


class Run(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_key: UUID
    tool_slug: str
    status: Literal["running", "succeeded", "failed"]
    output: str | None
    cost: int
    language: str
    error: str | None
    created_at: datetime
