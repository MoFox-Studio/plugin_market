"""Skill market: skills, versions, likes, ratings, comments, subscriptions.

Adds six new tables (``skills``, ``skill_versions``, ``skill_likes``,
``skill_ratings``, ``skill_comments``, ``skill_subscriptions``) and
extends the ``reviewaction`` enum with five new skill-management values
on PostgreSQL.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_skill_market"
down_revision = "0005_subscriptions_and_tokens"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

NEW_REVIEW_ACTIONS = (
    "PUBLISH_SKILL",
    "UPDATE_SKILL",
    "PUBLISH_SKILL_VERSION",
    "BLOCK_SKILL",
    "DELETE_SKILL",
)


def _is_postgres() -> bool:
    """Return True when running against PostgreSQL."""

    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    """Create the skill-market schema additions."""

    if _is_postgres():
        with op.get_context().autocommit_block():
            op.execute("CREATE TYPE IF NOT EXISTS skillstatus AS ENUM ('published', 'blocked')")
            for value in NEW_REVIEW_ACTIONS:
                op.execute(
                    f"ALTER TYPE reviewaction ADD VALUE IF NOT EXISTS '{value}'"
                )

    # ----- skills ----------------------------------------------------------
    op.create_table(
        "skills",
        sa.Column("skill_id", sa.String(length=120), primary_key=True),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "owner_id",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            nullable=False,
        ),
        sa.Column("icon_url", sa.String(length=1000), nullable=True),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("published", "blocked", name="skillstatus", create_type=False),
            nullable=False,
            server_default="published",
        ),
        sa.Column(
            "trust_level",
            sa.String(length=20),
            nullable=False,
            server_default="community",
        ),
        sa.Column(
            "download_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_skills_owner_id", "skills", ["owner_id"])
    op.create_index("ix_skills_status", "skills", ["status"])
    op.create_index(
        "idx_skills_status_trust",
        "skills",
        ["status", "trust_level"],
    )
    op.create_index("idx_skills_updated_at", "skills", ["updated_at"])

    # ----- skill_versions --------------------------------------------------
    op.create_table(
        "skill_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "skill_id",
            sa.String(length=120),
            sa.ForeignKey("skills.skill_id"),
            nullable=False,
        ),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("package_path", sa.String(length=500), nullable=False),
        sa.Column("package_size", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("release_notes", sa.Text(), nullable=True),
        sa.Column("min_mofox_version", sa.String(length=80), nullable=True),
        sa.Column(
            "download_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("skill_id", "version", name="uq_skill_version"),
    )
    op.create_index("ix_skill_versions_skill_id", "skill_versions", ["skill_id"])
    op.create_index("ix_skill_versions_version", "skill_versions", ["version"])

    # ----- skill_likes -----------------------------------------------------
    op.create_table(
        "skill_likes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "skill_id",
            sa.String(length=120),
            sa.ForeignKey("skills.skill_id"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("skill_id", "author_id", name="uq_skill_like"),
    )
    op.create_index("ix_skill_likes_skill_id", "skill_likes", ["skill_id"])
    op.create_index("ix_skill_likes_author_id", "skill_likes", ["author_id"])

    # ----- skill_ratings ---------------------------------------------------
    op.create_table(
        "skill_ratings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "skill_id",
            sa.String(length=120),
            sa.ForeignKey("skills.skill_id"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("skill_id", "author_id", name="uq_skill_rating"),
    )
    op.create_index("ix_skill_ratings_skill_id", "skill_ratings", ["skill_id"])
    op.create_index("ix_skill_ratings_author_id", "skill_ratings", ["author_id"])

    # ----- skill_comments --------------------------------------------------
    op.create_table(
        "skill_comments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "skill_id",
            sa.String(length=120),
            sa.ForeignKey("skills.skill_id"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("skill_comments.id"),
            nullable=True,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("mention_payload", sa.JSON(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_skill_comments_skill_id", "skill_comments", ["skill_id"])
    op.create_index("ix_skill_comments_author_id", "skill_comments", ["author_id"])
    op.create_index("ix_skill_comments_parent_id", "skill_comments", ["parent_id"])
    op.create_index("ix_skill_comments_created_at", "skill_comments", ["created_at"])
    op.create_index(
        "idx_skill_comments_skill_parent_created",
        "skill_comments",
        ["skill_id", "parent_id", "created_at"],
    )

    # ----- skill_subscriptions ---------------------------------------------
    op.create_table(
        "skill_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "skill_id",
            sa.String(length=120),
            sa.ForeignKey("skills.skill_id"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("skill_id", "author_id", name="uq_skill_subscription"),
    )
    op.create_index(
        "ix_skill_subscriptions_skill_id",
        "skill_subscriptions",
        ["skill_id"],
    )
    op.create_index(
        "ix_skill_subscriptions_author_id",
        "skill_subscriptions",
        ["author_id"],
    )
    op.create_index(
        "idx_skill_subscriptions_skill_created",
        "skill_subscriptions",
        ["skill_id", "created_at"],
    )


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    """Reverse all skill-market schema additions."""

    op.drop_index(
        "idx_skill_subscriptions_skill_created",
        table_name="skill_subscriptions",
    )
    op.drop_index(
        "ix_skill_subscriptions_author_id",
        table_name="skill_subscriptions",
    )
    op.drop_index(
        "ix_skill_subscriptions_skill_id",
        table_name="skill_subscriptions",
    )
    op.drop_table("skill_subscriptions")

    op.drop_index(
        "idx_skill_comments_skill_parent_created",
        table_name="skill_comments",
    )
    op.drop_index("ix_skill_comments_created_at", table_name="skill_comments")
    op.drop_index("ix_skill_comments_parent_id", table_name="skill_comments")
    op.drop_index("ix_skill_comments_author_id", table_name="skill_comments")
    op.drop_index("ix_skill_comments_skill_id", table_name="skill_comments")
    op.drop_table("skill_comments")

    op.drop_index("ix_skill_ratings_author_id", table_name="skill_ratings")
    op.drop_index("ix_skill_ratings_skill_id", table_name="skill_ratings")
    op.drop_table("skill_ratings")

    op.drop_index("ix_skill_likes_author_id", table_name="skill_likes")
    op.drop_index("ix_skill_likes_skill_id", table_name="skill_likes")
    op.drop_table("skill_likes")

    op.drop_index("ix_skill_versions_version", table_name="skill_versions")
    op.drop_index("ix_skill_versions_skill_id", table_name="skill_versions")
    op.drop_table("skill_versions")

    op.drop_index("idx_skills_updated_at", table_name="skills")
    op.drop_index("idx_skills_status_trust", table_name="skills")
    op.drop_index("ix_skills_status", table_name="skills")
    op.drop_index("ix_skills_owner_id", table_name="skills")
    op.drop_table("skills")

    # NOTE: PostgreSQL does not support removing values from an enum type.
    # The new ``reviewaction`` values added in upgrade() are intentionally
    # left in place during downgrade; they are unused but harmless.
    if _is_postgres():
        with op.get_context().autocommit_block():
            op.execute("DROP TYPE IF EXISTS skillstatus")