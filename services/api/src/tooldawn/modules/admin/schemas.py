from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from tooldawn.modules.ai_tools.registry import TOOLS
from tooldawn.modules.catalog.schemas import Tool
from tooldawn.modules.operations.capabilities import Capability

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
    model_group_id: UUID | None = None
    model_capability: Capability | None = None
    name: ShortText
    summary: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=10000)
    category: Slug
    icon: Icon = "wrench"
    color: Color = "blue"
    kind: Literal["internal"] = "internal"
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
        if self.slug in TOOLS:
            if self.model_capability not in (None, "text"):
                raise ValueError("文字工具仅支持文字生成能力")
            self.model_capability = "text"
        if self.model_group_id and not self.model_capability:
            raise ValueError("绑定分组前请选择所需能力")
        if self.external_url is not None:
            raise ValueError("本站工具不支持站外地址")
        if self.slug == "image-generate":
            if self.model_capability not in (None, "image_generate"):
                raise ValueError("图片生成工具仅支持图片生成能力")
            self.model_capability = "image_generate"
        if self.status == "available" and self.slug not in {*TOOLS, "image-generate"}:
            raise ValueError("工作台尚未实现，请保持开发中")
        return self


class AdminTool(Tool):
    model_group_id: UUID | None = None
    model_capability: Capability | None = None
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
