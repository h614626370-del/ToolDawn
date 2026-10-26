"""Image workbench reference uploads and safe generation metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0014_image_studio"
down_revision = "0013_image_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "image_jobs", sa.Column("options", sa.JSON(), nullable=False, server_default="{}")
    )
    op.create_table(
        "image_references",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("encrypted_image", sa.Text(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_image_references_user_id", "image_references", ["user_id"])
    op.create_index("ix_image_references_expires_at", "image_references", ["expires_at"])


def downgrade():
    op.drop_table("image_references")
    op.drop_column("image_jobs", "options")
