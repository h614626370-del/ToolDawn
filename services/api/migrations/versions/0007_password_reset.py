"""Separate login and password reset challenges."""

import sqlalchemy as sa
from alembic import op

revision = "0007_password_reset"
down_revision = "0006_operations"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "email_challenges",
        sa.Column("purpose", sa.String(20), nullable=False, server_default="login"),
    )


def downgrade():
    op.drop_column("email_challenges", "purpose")
