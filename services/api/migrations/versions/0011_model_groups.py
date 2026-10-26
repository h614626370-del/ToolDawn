"""Capability-based account groups and shared failover health."""

import sqlalchemy as sa
from alembic import op

revision = "0011_model_groups"
down_revision = "0010_announcements"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "model_groups",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "model_group_members",
        sa.Column(
            "group_id",
            sa.Uuid(),
            sa.ForeignKey("model_groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("model_accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("priority", sa.Integer(), nullable=False),
    )
    op.add_column(
        "model_accounts",
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default='["text"]'),
    )
    for name in ("cooldown_until", "last_failure_at"):
        op.add_column("model_accounts", sa.Column(name, sa.DateTime(timezone=True)))
    op.add_column("model_accounts", sa.Column("last_failure_code", sa.String(40)))
    op.add_column("tools", sa.Column("model_group_id", sa.Uuid(), sa.ForeignKey("model_groups.id")))
    op.create_index("ix_tools_model_group_id", "tools", ["model_group_id"])
    op.add_column("tools", sa.Column("model_capability", sa.String(30)))
    op.add_column(
        "text_tool_runs",
        sa.Column("group_id", sa.Uuid(), sa.ForeignKey("model_groups.id", ondelete="SET NULL")),
    )
    op.add_column(
        "text_tool_runs", sa.Column("attempts", sa.JSON(), nullable=False, server_default="[]")
    )


def downgrade():
    op.drop_column("text_tool_runs", "attempts")
    op.drop_column("text_tool_runs", "group_id")
    op.drop_column("tools", "model_capability")
    op.drop_index("ix_tools_model_group_id", "tools")
    op.drop_column("tools", "model_group_id")
    for name in ("last_failure_code", "last_failure_at", "cooldown_until", "capabilities"):
        op.drop_column("model_accounts", name)
    op.drop_table("model_group_members")
    op.drop_table("model_groups")
