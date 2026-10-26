"""Durable image jobs and on-site image generation tool."""

import sqlalchemy as sa
from alembic import op

revision = "0013_image_jobs"
down_revision = "0012_account_model_routing"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "image_jobs",
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("text_tool_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("payload", sa.Text()),
        sa.Column("claimed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("image", sa.LargeBinary()),
        sa.Column("media_type", sa.String(30)),
    )
    op.execute("""
        INSERT INTO tools (slug, name, summary, description, category, icon, color, kind,
          status, featured, keywords, features, updated_at, sort_order, published, revision,
          model_capability)
        SELECT 'image-generate', 'AI 图片生成', '描述你的想法，生成一张属于你的图片。',
          '输入画面描述，选择图片比例，生成后即可预览和下载。支持中文描述，适合插画、产品概念和创意配图。',
          slug, 'image', 'violet', 'internal', 'available', true,
          '["AI", "生图", "文生图", "image", "generate"]'::json,
          '["文字生成图片", "三种图片比例", "生成记录与下载"]'::json,
          CURRENT_DATE, 0, true, 1, 'image_generate'
        FROM categories WHERE slug = 'image'
        ON CONFLICT (slug) DO NOTHING
    """)


def downgrade():
    op.drop_table("image_jobs")
    op.execute("DELETE FROM tools WHERE slug = 'image-generate'")
