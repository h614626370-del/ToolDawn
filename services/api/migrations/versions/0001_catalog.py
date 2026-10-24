"""Create the initial public catalog."""

import sqlalchemy as sa
from alembic import op

revision = "0001_catalog"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("slug", sa.String(80), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("icon", sa.String(50), nullable=False),
        sa.Column("color", sa.String(30), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )
    op.create_table(
        "tools",
        sa.Column("slug", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("summary", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(80), sa.ForeignKey("categories.slug"), nullable=False),
        sa.Column("icon", sa.String(50), nullable=False),
        sa.Column("color", sa.String(30), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("external_url", sa.Text(), nullable=True),
        sa.Column("image", sa.Text(), nullable=True),
        sa.Column("featured", sa.Boolean(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.Date(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint("kind IN ('internal', 'external')", name="tools_kind"),
        sa.CheckConstraint("status IN ('available', 'coming_soon')", name="tools_status"),
        sa.CheckConstraint(
            "(kind = 'external' AND external_url IS NOT NULL AND external_url LIKE 'https://%') OR "
            "(kind = 'internal' AND external_url IS NULL)",
            name="tools_destination",
        ),
    )
    for column in ("category", "featured", "sort_order"):
        op.create_index(f"ix_tools_{column}", "tools", [column])


def downgrade() -> None:
    op.drop_table("tools")
    op.drop_table("categories")
