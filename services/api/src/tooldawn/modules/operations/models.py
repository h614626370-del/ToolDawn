from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tooldawn.infra.database import Base


class SettingRecord(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ModelAccount(Base):
    __tablename__ = "model_accounts"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    base_url: Mapped[str] = mapped_column(String(500))
    encrypted_key: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_test_ms: Mapped[int | None] = mapped_column(Integer)


class TicketRecord(Base):
    __tablename__ = "support_tickets"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class TicketMessage(Base):
    __tablename__ = "ticket_messages"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("support_tickets.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    staff: Mapped[bool] = mapped_column(Boolean)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
