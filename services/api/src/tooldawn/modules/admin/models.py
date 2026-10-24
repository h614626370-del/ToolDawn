from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from tooldawn.infra.database import Base


class AuditRecord(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    actor_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    action: Mapped[str] = mapped_column(String(50))
    target: Mapped[str] = mapped_column(String(150))
    changed_fields: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
