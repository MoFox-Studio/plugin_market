"""Add community tables: likes, ratings, comments, plus version download_count."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_community"
down_revision = "0002_github_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add community engagement tables."""

    op.add_column(
        "plugin_versions",
        sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "plugin_likes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plugin_id", sa.String(length=120), sa.ForeignKey("plugins.plugin_id"), nullable=False),
        sa.Column("author_id", sa.String(length=120), sa.ForeignKey("authors.author_id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("plugin_id", "author_id", name="uq_plugin_like"),
    )
    op.create_index("ix_plugin_likes_plugin_id", "plugin_likes", ["plugin_id"])
    op.create_index("ix_plugin_likes_author_id", "plugin_likes", ["author_id"])
    op.create_table(
        "plugin_ratings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plugin_id", sa.String(length=120), sa.ForeignKey("plugins.plugin_id"), nullable=False),
        sa.Column("author_id", sa.String(length=120), sa.ForeignKey("authors.author_id"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("plugin_id", "author_id", name="uq_plugin_rating"),
    )
    op.create_index("ix_plugin_ratings_plugin_id", "plugin_ratings", ["plugin_id"])
    op.create_index("ix_plugin_ratings_author_id", "plugin_ratings", ["author_id"])
    op.create_table(
        "plugin_comments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plugin_id", sa.String(length=120), sa.ForeignKey("plugins.plugin_id"), nullable=False),
        sa.Column("author_id", sa.String(length=120), sa.ForeignKey("authors.author_id"), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("plugin_comments.id"), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_plugin_comments_plugin_id", "plugin_comments", ["plugin_id"])
    op.create_index("ix_plugin_comments_author_id", "plugin_comments", ["author_id"])
    op.create_index("ix_plugin_comments_parent_id", "plugin_comments", ["parent_id"])
    op.create_index("ix_plugin_comments_created_at", "plugin_comments", ["created_at"])


def downgrade() -> None:
    """Remove community engagement tables."""

    op.drop_index("ix_plugin_comments_created_at", table_name="plugin_comments")
    op.drop_index("ix_plugin_comments_parent_id", table_name="plugin_comments")
    op.drop_index("ix_plugin_comments_author_id", table_name="plugin_comments")
    op.drop_index("ix_plugin_comments_plugin_id", table_name="plugin_comments")
    op.drop_table("plugin_comments")
    op.drop_index("ix_plugin_ratings_author_id", table_name="plugin_ratings")
    op.drop_index("ix_plugin_ratings_plugin_id", table_name="plugin_ratings")
    op.drop_table("plugin_ratings")
    op.drop_index("ix_plugin_likes_author_id", table_name="plugin_likes")
    op.drop_index("ix_plugin_likes_plugin_id", table_name="plugin_likes")
    op.drop_table("plugin_likes")
    op.drop_column("plugin_versions", "download_count")
