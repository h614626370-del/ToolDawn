"""Groups are account collections; capabilities and models belong to accounts."""

import sqlalchemy as sa
from alembic import op

revision = "0012_account_model_routing"
down_revision = "0011_model_groups"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("model_groups", "capabilities")
    op.add_column(
        "model_accounts",
        sa.Column("capability_models", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade():
    op.drop_column("model_accounts", "capability_models")
    op.add_column(
        "model_groups",
        sa.Column(
            "capabilities",
            sa.JSON(),
            nullable=False,
            server_default='["text", "image_generate", "image_edit", "vision"]',
        ),
    )
