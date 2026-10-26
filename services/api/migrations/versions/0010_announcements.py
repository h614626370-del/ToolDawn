"""Add announcements with revision-aware user read receipts."""

import sqlalchemy as sa
from alembic import op

revision = "0010_announcements"
down_revision = "0009_internal_tools_only"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "announcements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("notify_mode", sa.String(20), nullable=False),
        sa.Column("audience", sa.String(20), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'active', 'archived')", name="announcement_status"),
        sa.CheckConstraint("notify_mode IN ('silent', 'popup')", name="announcement_notify_mode"),
        sa.CheckConstraint("audience IN ('all', 'members')", name="announcement_audience"),
        sa.CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="announcement_window",
        ),
    )
    op.create_index("ix_announcements_status", "announcements", ["status"])
    op.create_table(
        "announcement_reads",
        sa.Column(
            "announcement_id",
            sa.Uuid(),
            sa.ForeignKey("announcements.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("announcement_reads")
    op.drop_table("announcements")
