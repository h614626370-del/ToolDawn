from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tooldawn.infra.database import Base


class TextRunRecord(Base):
    __tablename__ = "text_tool_runs"
    __table_args__ = (
        UniqueConstraint("user_id", "request_key", name="text_run_request"),
        CheckConstraint("status IN ('running', 'succeeded', 'failed')", name="text_run_status"),
        CheckConstraint("cost >= 0", name="text_run_cost"),
        Index("ix_text_runs_owner_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    request_key: Mapped[UUID] = mapped_column()
    fingerprint: Mapped[str] = mapped_column(String(64))
    tool_slug: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20))
    output: Mapped[str | None] = mapped_column(Text)
    cost: Mapped[int] = mapped_column()
    language: Mapped[str] = mapped_column(String(5))
    error: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("model_accounts.id", ondelete="SET NULL")
    )
    model: Mapped[str | None] = mapped_column(String(120))
    duration_ms: Mapped[int | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
