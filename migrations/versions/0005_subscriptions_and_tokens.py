"""添加订阅、关注和单槽位访问令牌。

新增 ``author_follows``、``plugin_subscriptions`` 和 ``author_access_tokens``。
将现有 ``plugin_likes`` 记录复制到 ``plugin_subscriptions``，
使原来的点赞意图转为新的订阅状态。
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_subscriptions_and_tokens"
down_revision = "0004_overhaul_phase1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "author_follows",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "follower_id",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("follower_id", "author_id", name="uq_author_follow"),
    )
    op.create_index("ix_author_follows_follower_id", "author_follows", ["follower_id"])
    op.create_index("ix_author_follows_author_id", "author_follows", ["author_id"])
    op.create_index(
        "idx_author_follows_author_created",
        "author_follows",
        ["author_id", "created_at"],
    )

    op.create_table(
        "plugin_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "plugin_id",
            sa.String(length=120),
            sa.ForeignKey("plugins.plugin_id"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("plugin_id", "author_id", name="uq_plugin_subscription"),
    )
    op.create_index(
        "ix_plugin_subscriptions_plugin_id",
        "plugin_subscriptions",
        ["plugin_id"],
    )
    op.create_index(
        "ix_plugin_subscriptions_author_id",
        "plugin_subscriptions",
        ["author_id"],
    )
    op.create_index(
        "idx_plugin_subscriptions_plugin_created",
        "plugin_subscriptions",
        ["plugin_id", "created_at"],
    )

    op.create_table(
        "author_access_tokens",
        sa.Column(
            "author_id",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            primary_key=True,
        ),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("token_preview", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_author_access_token_hash"),
    )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO plugin_subscriptions (plugin_id, author_id, created_at)
            SELECT plugin_id, author_id, created_at
            FROM plugin_likes
            """
        )
    )


def downgrade() -> None:
    op.drop_table("author_access_tokens")
    op.drop_index("idx_plugin_subscriptions_plugin_created", table_name="plugin_subscriptions")
    op.drop_index("ix_plugin_subscriptions_author_id", table_name="plugin_subscriptions")
    op.drop_index("ix_plugin_subscriptions_plugin_id", table_name="plugin_subscriptions")
    op.drop_table("plugin_subscriptions")
    op.drop_index("idx_author_follows_author_created", table_name="author_follows")
    op.drop_index("ix_author_follows_author_id", table_name="author_follows")
    op.drop_index("ix_author_follows_follower_id", table_name="author_follows")
    op.drop_table("author_follows")