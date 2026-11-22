"""Add opt-in recommendation preferences and expiring explicit feedback."""

from alembic import op
import sqlalchemy as sa

revision = "0008_recommendation_preferences"
down_revision = "0007_skill_readme_markdown"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendation_preferences",
        sa.Column("author_id", sa.String(120), sa.ForeignKey("authors.author_id"), primary_key=True),
        sa.Column("personalization_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "recommendation_feedback",
        sa.Column("author_id", sa.String(120), sa.ForeignKey("authors.author_id"), primary_key=True),
        sa.Column("kind", sa.String(24), primary_key=True),
        sa.Column("target", sa.String(120), primary_key=True),
        sa.Column("reason", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_recommendation_feedback_expiry", "recommendation_feedback", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_recommendation_feedback_expiry", table_name="recommendation_feedback")
    op.drop_table("recommendation_feedback")
    op.drop_table("recommendation_preferences")
