"""Email challenges, users and revocable sessions."""

import sqlalchemy as sa
from alembic import op

revision = "0002_auth"
down_revision = "0001_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("disabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user', 'admin')", name="users_role"),
    )
    op.create_table(
        "email_challenges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("code_digest", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_email_challenges_expires_at", "email_challenges", ["expires_at"])
    op.create_table(
        "sessions",
        sa.Column("token_digest", sa.String(64), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_table("sessions")
    op.drop_table("email_challenges")
    op.drop_table("users")
