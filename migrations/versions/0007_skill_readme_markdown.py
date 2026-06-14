"""Add readme_markdown column to skills table.

Stores the full SKILL.md body (everything after the YAML front matter)
so the market frontend can render a proper preview.
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
