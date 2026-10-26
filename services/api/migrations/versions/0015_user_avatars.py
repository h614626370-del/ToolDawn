"""Private profile avatars, kept separate from session user reads."""

import sqlalchemy as sa
from alembic import op

revision = "0015_user_avatars"
down_revision = "0014_image_studio"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("avatar_revision", sa.Uuid(), nullable=True))
    op.create_table(
        "user_avatars",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("image", sa.LargeBinary(), nullable=False),
    )


def downgrade():
    op.drop_table("user_avatars")
    op.drop_column("users", "avatar_revision")
