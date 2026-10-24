from datetime import date

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tooldawn.infra.database import Base


class CategoryRecord(Base):
    __tablename__ = "categories"

    slug: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    icon: Mapped[str] = mapped_column(String(50))
    color: Mapped[str] = mapped_column(String(30))
    sort_order: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class ToolRecord(Base):
    __tablename__ = "tools"
    __table_args__ = (
        CheckConstraint("kind IN ('internal', 'external')", name="tools_kind"),
        CheckConstraint("status IN ('available', 'coming_soon')", name="tools_status"),
        CheckConstraint(
            "(kind = 'external' AND external_url IS NOT NULL AND external_url LIKE 'https://%') OR "
            "(kind = 'internal' AND external_url IS NULL)",
            name="tools_destination",
        ),
    )

    slug: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(ForeignKey("categories.slug"), index=True)
    icon: Mapped[str] = mapped_column(String(50))
    color: Mapped[str] = mapped_column(String(30))
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    external_url: Mapped[str | None] = mapped_column(Text)
    image: Mapped[str | None] = mapped_column(Text)
    featured: Mapped[bool] = mapped_column(Boolean, index=True)
    keywords: Mapped[list[str]] = mapped_column(JSON)
    features: Mapped[list[str]] = mapped_column(JSON)
    updated_at: Mapped[date] = mapped_column(Date)
    sort_order: Mapped[int] = mapped_column(Integer, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
