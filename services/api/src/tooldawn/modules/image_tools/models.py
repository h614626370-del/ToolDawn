from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tooldawn.infra.database import Base


class ImageJob(Base):
    __tablename__ = "image_jobs"

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("text_tool_runs.id", ondelete="CASCADE"), primary_key=True
    )
    payload: Mapped[str | None] = mapped_column(Text)
    claimed: Mapped[bool] = mapped_column(Boolean, default=False)
    image: Mapped[bytes | None] = mapped_column(LargeBinary)
    media_type: Mapped[str | None] = mapped_column(String(30))
    options: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")


class ImageReference(Base):
    __tablename__ = "image_references"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    encrypted_image: Mapped[str] = mapped_column(Text)
    width: Mapped[int] = mapped_column()
    height: Mapped[int] = mapped_column()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
