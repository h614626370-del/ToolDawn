"""Persist text-tool receipts and generated results."""

import sqlalchemy as sa
from alembic import op

revision = "0005_text_tools"
down_revision = "0004_billing"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "text_tool_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_key", sa.Uuid(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("tool_slug", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("output", sa.Text()),
        sa.Column("cost", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(5), nullable=False),
        sa.Column("error", sa.String(300)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "request_key", name="text_run_request"),
        sa.CheckConstraint("status IN ('running', 'succeeded', 'failed')", name="text_run_status"),
        sa.CheckConstraint("cost >= 0", name="text_run_cost"),
    )
    op.create_index("ix_text_runs_owner_created", "text_tool_runs", ["user_id", "created_at"])


def downgrade():
    op.drop_table("text_tool_runs")
