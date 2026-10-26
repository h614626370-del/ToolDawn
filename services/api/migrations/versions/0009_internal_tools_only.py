"""Remove external catalog entries and prevent their recreation."""

from alembic import op

revision = "0009_internal_tools_only"
down_revision = "0008_payment_providers"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DELETE FROM tools WHERE kind = 'external'")
    op.create_check_constraint("tools_internal_only", "tools", "kind = 'internal'")


def downgrade():
    # Removed catalog content is not recreated on downgrade.
    op.drop_constraint("tools_internal_only", "tools", type_="check")
