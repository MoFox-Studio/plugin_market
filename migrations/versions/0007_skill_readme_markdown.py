"""为 skills 表添加 readme_markdown 列。

存储 SKILL.md 的完整正文（YAML 前置元数据之后的全部内容），
供市场前端正确渲染预览。
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_skill_readme_markdown"
down_revision = "0006_skill_market"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("skills", sa.Column("readme_markdown", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("skills", "readme_markdown")
