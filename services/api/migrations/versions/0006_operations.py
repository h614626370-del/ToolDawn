"""Administration, model accounts, profile security and support."""

import sqlalchemy as sa
from alembic import op

revision = "0006_operations"
down_revision = "0005_text_tools"
branch_labels = None
depends_on = None


def upgrade():
    for column in (
        sa.Column("display_name", sa.String(60), nullable=False, server_default=""),
        sa.Column("password_hash", sa.String(250)),
        sa.Column("is_superadmin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    ):
        op.add_column("users", column)
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "model_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("encrypted_key", sa.Text(), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_test_at", sa.DateTime(timezone=True)),
        sa.Column("last_test_ok", sa.Boolean()),
        sa.Column("last_test_ms", sa.Integer()),
    )
    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject", sa.String(120), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('open', 'processing', 'replied', 'closed')", name="ticket_status"
        ),
    )
    op.create_index("ix_support_tickets_user_id", "support_tickets", ["user_id"])
    op.create_index("ix_support_tickets_updated_at", "support_tickets", ["updated_at"])
    op.create_table(
        "ticket_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.Uuid(),
            sa.ForeignKey("support_tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("staff", sa.Boolean(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ticket_messages_ticket_id", "ticket_messages", ["ticket_id"])
    for column in (
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("model_accounts.id", ondelete="SET NULL")),
        sa.Column("model", sa.String(120)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    ):
        op.add_column("text_tool_runs", column)
    op.create_index("ix_text_runs_created", "text_tool_runs", ["created_at"])


def downgrade():
    op.drop_index("ix_text_runs_created", table_name="text_tool_runs")
    for name in ("completed_at", "duration_ms", "model", "account_id"):
        op.drop_column("text_tool_runs", name)
    op.drop_table("ticket_messages")
    op.drop_table("support_tickets")
    op.drop_table("model_accounts")
    op.drop_table("system_settings")
    for name in ("must_change_password", "is_superadmin", "password_hash", "display_name"):
        op.drop_column("users", name)
