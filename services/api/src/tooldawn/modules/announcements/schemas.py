from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Status = Literal["draft", "active", "archived"]


class AnnouncementInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=30000)
    status: Status = "draft"
    notify_mode: Literal["silent", "popup"] = "silent"
    audience: Literal["all", "members"] = "all"
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    revision: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def valid_window(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("结束时间必须晚于开始时间。")
        return self


class AnnouncementView(AnnouncementInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    updated_at: datetime


class PublicAnnouncement(AnnouncementView):
    read_at: datetime | None = None


class AdminAnnouncement(AnnouncementView):
    read_count: int = 0


class AnnouncementPage(BaseModel):
    items: list[PublicAnnouncement]
    total: int
    unread_count: int
    popups: list[PublicAnnouncement]
    guest_versions: dict[str, int] = Field(default_factory=dict)


class AdminAnnouncementPage(BaseModel):
    items: list[AdminAnnouncement]
    total: int


class ReadReceipt(BaseModel):
    id: UUID
    revision: int = Field(ge=1)


class ReadInput(BaseModel):
    items: list[ReadReceipt] = Field(min_length=1, max_length=100)
