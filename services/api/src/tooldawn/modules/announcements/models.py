from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tooldawn.infra.database import Base


class Announcement(Base):
    __tablename__ = "announcements"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'active', 'archived')", name="announcement_status"),
        CheckConstraint("notify_mode IN ('silent', 'popup')", name="announcement_notify_mode"),
        CheckConstraint("audience IN ('all', 'members')", name="announcement_audience"),
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="announcement_window",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), index=True)
    notify_mode: Mapped[str] = mapped_column(String(20))
    audience: Mapped[str] = mapped_column(String(20))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AnnouncementRead(Base):
    __tablename__ = "announcement_reads"
    announcement_id: Mapped[UUID] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    revision: Mapped[int] = mapped_column(Integer)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
