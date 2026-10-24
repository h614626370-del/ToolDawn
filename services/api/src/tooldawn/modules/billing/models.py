from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from tooldawn.infra.database import Base


class WalletRecord(Base):
    __tablename__ = "credit_wallets"
    __table_args__ = (CheckConstraint("balance >= 0", name="wallet_nonnegative"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    balance: Mapped[int] = mapped_column(BigInteger, default=0)


class CreditRecord(Base):
    __tablename__ = "credit_entries"
    __table_args__ = (
        UniqueConstraint("user_id", "reference", name="credit_reference"),
        CheckConstraint("amount != 0 AND balance_after >= 0", name="credit_valid"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    balance_after: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(20))
    reference: Mapped[str] = mapped_column(String(150))
    reason: Mapped[str] = mapped_column(String(300))
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class OrderRecord(Base):
    __tablename__ = "payment_orders"
    __table_args__ = (
        UniqueConstraint("user_id", "request_key", name="order_request_key"),
        CheckConstraint("credits > 0 AND unit_amount > 0", name="order_positive"),
        CheckConstraint("status IN ('pending', 'paid', 'expired', 'failed')", name="order_status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    request_key: Mapped[UUID] = mapped_column(Uuid)
    package_id: Mapped[str] = mapped_column(String(50))
    credits: Mapped[int] = mapped_column(BigInteger)
    unit_amount: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    checkout_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    checkout_url: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
