"""Payment provider instances and immutable order routing."""

import sqlalchemy as sa
from alembic import op

revision = "0008_payment_providers"
down_revision = "0007_password_reset"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payment_providers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("config", sa.Text(), nullable=False),
        sa.Column("methods", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "payment_orders",
        sa.Column("provider_id", sa.Uuid(), sa.ForeignKey("payment_providers.id"), nullable=True),
    )
    for name, length, default in (
        ("provider_key", 20, "stripe"),
        ("provider_name", 80, "Stripe"),
        ("payment_method", 20, "card"),
    ):
        op.add_column(
            "payment_orders",
            sa.Column(name, sa.String(length), nullable=False, server_default=default),
        )
    op.add_column("payment_orders", sa.Column("provider_trade_id", sa.String(255)))
    op.add_column("payment_orders", sa.Column("qr_code", sa.Text()))
    op.alter_column("payment_orders", "checkout_url", type_=sa.Text())
    op.create_index("ix_payment_orders_provider_id", "payment_orders", ["provider_id"])
    op.create_unique_constraint(
        "provider_transaction_once", "payment_orders", ["provider_id", "provider_trade_id"]
    )


def downgrade():
    op.drop_constraint("provider_transaction_once", "payment_orders", type_="unique")
    op.drop_index("ix_payment_orders_provider_id", table_name="payment_orders")
    for column in (
        "qr_code",
        "provider_trade_id",
        "payment_method",
        "provider_name",
        "provider_key",
        "provider_id",
    ):
        op.drop_column("payment_orders", column)
    op.drop_table("payment_providers")
