from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from tooldawn.modules.catalog.schemas import Tool

Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)]
Color = Literal["green", "blue", "coral", "violet", "amber"]
Icon = Literal[
    "image",
    "text",
    "coffee",
    "wrench",
    "bookmark",
    "heart",
    "sun",
    "compass",
    "sparkles",
    "gift",
    "compress",
    "pen",
    "scissors",
    "layers",
    "code",
    "grid",
]
ShortText = Annotated[str, Field(min_length=1, max_length=100)]
ListText = Annotated[str, Field(min_length=1, max_length=100)]


class CategoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    slug: Slug
    name: ShortText
    icon: Icon = "grid"
    color: Color = "green"
    sort_order: int = Field(default=0, ge=0, le=100000)
    revision: int = Field(default=1, ge=1)


class AdminCategory(CategoryInput):
    tool_count: int


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    slug: Slug
    name: ShortText
    summary: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=10000)
    category: Slug
    icon: Icon = "wrench"
    color: Color = "blue"
    kind: Literal["internal", "external"]
    status: Literal["available", "coming_soon"]
    external_url: HttpUrl | None = None
    image: str | None = Field(default=None, pattern=r"^/images/[a-zA-Z0-9_-]+\.(jpg|png|webp)$")
    featured: bool = False
    published: bool = False
    keywords: list[ListText] = Field(default_factory=list, max_length=30)
    features: list[ListText] = Field(default_factory=list, max_length=20)
    sort_order: int = Field(default=0, ge=0, le=100000)
    revision: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def destination(self):
        if self.kind == "external":
            if (
                not self.external_url
                or self.external_url.scheme != "https"
                or self.external_url.username
                or self.external_url.password
            ):
                raise ValueError("站外工具需要不含账号密码的 HTTPS 地址")
        elif self.external_url is not None or self.status == "available":
            raise ValueError("本站工作台尚未实现，请保持开发中且不填写站外地址")
        return self


class AdminTool(Tool):
    published: bool
    revision: int


class AdminToolPage(BaseModel):
    items: list[AdminTool]
    total: int


class AdminUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: Literal["user", "admin"]
    disabled: bool
    created_at: datetime


class AdminUserPage(BaseModel):
    items: list[AdminUser]
    total: int


class UserState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disabled: bool
