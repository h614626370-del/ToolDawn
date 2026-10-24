from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class Category(BaseModel):
    slug: str
    name: str
    icon: str
    color: str


class CategorySummary(Category):
    tool_count: int


class Tool(BaseModel):
    slug: str
    name: str
    summary: str
    description: str
    category: str
    icon: str
    color: str
    kind: Literal["internal", "external"]
    status: Literal["available", "coming_soon"]
    external_url: HttpUrl | None = None
    image: str | None = None
    featured: bool = False
    keywords: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    updated_at: date
    sort_order: int

    @model_validator(mode="after")
    def validate_destination(self) -> "Tool":
        if self.kind == "external" and (
            self.external_url is None or self.external_url.scheme != "https"
        ):
            raise ValueError("External tools require an HTTPS destination")
        if self.kind == "internal" and self.external_url is not None:
            raise ValueError("Internal tools must not have external destinations")
        return self


class ToolPage(BaseModel):
    items: list[Tool]
    total: int
    next_cursor: int | None
