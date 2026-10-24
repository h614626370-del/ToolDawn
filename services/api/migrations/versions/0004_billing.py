"""Credit ledger and immutable payment order snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0004_billing"
down_revision = "0003_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_wallets",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("balance", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("balance >= 0", name="wallet_nonnegative"),
    )
    op.create_table(
        "credit_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("reference", sa.String(150), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "reference", name="credit_reference"),
        sa.CheckConstraint("amount != 0 AND balance_after >= 0", name="credit_valid"),
    )
    op.create_index("ix_credit_entries_user_id", "credit_entries", ["user_id"])
    op.create_index("ix_credit_entries_created_at", "credit_entries", ["created_at"])
    op.create_table(
        "payment_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_key", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.String(50), nullable=False),
        sa.Column("credits", sa.BigInteger(), nullable=False),
        sa.Column("unit_amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("checkout_id", sa.String(255), unique=True),
        sa.Column("checkout_url", sa.String(2048)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "request_key", name="order_request_key"),
        sa.CheckConstraint("credits > 0 AND unit_amount > 0", name="order_positive"),
        sa.CheckConstraint(
            "status IN ('pending', 'paid', 'expired', 'failed')", name="order_status"
        ),
    )
    op.create_index("ix_payment_orders_user_id", "payment_orders", ["user_id"])
    op.create_index("ix_payment_orders_created_at", "payment_orders", ["created_at"])


def downgrade() -> None:
    for name in ("payment_orders", "credit_entries", "credit_wallets"):
        op.drop_table(name)
