"""Publication state, optimistic edits and administrator audit trail."""

import sqlalchemy as sa
from alembic import op

revision = "0003_admin"
down_revision = "0002_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tools", sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.add_column("tools", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(
        "categories", sa.Column("revision", sa.Integer(), nullable=False, server_default="1")
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("target", sa.String(150), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_column("categories", "revision")
    op.drop_column("tools", "revision")
    op.drop_column("tools", "published")
