"""Plugin market overhaul phase 1: profiles, pins, curation, announcements, inbox.

Adds eight new tables (`author_profiles`, `pinned_plugins`, `curation_entries`,
`announcements`, `announcement_dismissals`, `inbox_messages`, `comment_mentions`,
`plugin_metadata_changes`), the new ``mention_payload`` JSON column on
``plugin_comments`` and six supporting indexes (Plugin status/trust, plugin
updated-at, comment fan-out, inbox lookup, pinned-author scan, curation slot
lookup). On PostgreSQL the ``reviewaction`` enum type is extended with the new
governance + bulk action values; SQLite stores enums as plain strings so it
needs no DDL for the enum extension.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_overhaul_phase1"
down_revision = "0003_community"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

NEW_REVIEW_ACTIONS = (
    "CREATE_CURATION",
    "UPDATE_CURATION",
    "DISABLE_CURATION",
    "CREATE_ANNOUNCEMENT",
    "UPDATE_ANNOUNCEMENT",
    "ARCHIVE_ANNOUNCEMENT",
    "INLINE_EDIT_PLUGIN",
    "BULK_PUBLISH",
    "BULK_REJECT",
    "BULK_BLOCK",
    "BULK_DEPRECATE",
    "BULK_SET_TRUST_LEVEL",
    "BULK_DELETE",
)


def _is_postgres() -> bool:
    """Return True when running against PostgreSQL."""

    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    """Create the phase-1 overhaul schema additions."""

    if _is_postgres():
        # ``ALTER TYPE ... ADD VALUE`` must run outside a transaction in
        # PostgreSQL; ``IF NOT EXISTS`` makes the statement idempotent for
        # re-runs / down-then-up sequences.
        with op.get_context().autocommit_block():
            for value in NEW_REVIEW_ACTIONS:
                op.execute(
                    f"ALTER TYPE reviewaction ADD VALUE IF NOT EXISTS '{value}'"
                )

    # ----- author_profiles ------------------------------------------------
    op.create_table(
        "author_profiles",
        sa.Column(
            "author_id",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            primary_key=True,
        ),
        sa.Column("bio", sa.Text(), nullable=False, server_default=""),
        sa.Column("background_image_url", sa.String(length=1000), nullable=True),
        sa.Column(
            "background_image_kind",
            sa.String(length=16),
            nullable=False,
            server_default="url",
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ----- pinned_plugins -------------------------------------------------
    op.create_table(
        "pinned_plugins",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "author_id",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            nullable=False,
        ),
        sa.Column(
            "plugin_id",
            sa.String(length=120),
            sa.ForeignKey("plugins.plugin_id"),
            nullable=False,
        ),
        sa.Column("pinned_reason", sa.String(length=200), nullable=True),
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("author_id", "plugin_id", name="unique_pinned"),
    )
    op.create_index("ix_pinned_plugins_author_id", "pinned_plugins", ["author_id"])
    op.create_index("ix_pinned_plugins_plugin_id", "pinned_plugins", ["plugin_id"])
    op.create_index(
        "idx_pinned_author",
        "pinned_plugins",
        ["author_id", "pinned_at"],
    )

    # ----- curation_entries -----------------------------------------------
    op.create_table(
        "curation_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slot_type", sa.String(length=40), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.String(length=240), nullable=False),
        sa.Column(
            "signature_plugin_id",
            sa.String(length=120),
            sa.ForeignKey("plugins.plugin_id"),
            nullable=True,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audience", sa.String(length=40), nullable=False, server_default="all"),
        sa.Column("display_meta", sa.JSON(), nullable=False),
        sa.Column(
            "created_by",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_curation_entries_slot_type", "curation_entries", ["slot_type"])
    op.create_index(
        "idx_curation_enabled_sort",
        "curation_entries",
        ["enabled", "sort_order"],
    )

    # ----- announcements --------------------------------------------------
    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "display_mode", sa.String(length=20), nullable=False, server_default="banner"
        ),
        sa.Column(
            "severity", sa.String(length=20), nullable=False, server_default="info"
        ),
        sa.Column(
            "dismissible", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audience", sa.String(length=40), nullable=False, server_default="all"),
        sa.Column(
            "emit_inbox", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("dismiss_token", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_by",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ----- announcement_dismissals ---------------------------------------
    op.create_table(
        "announcement_dismissals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "announcement_id",
            sa.Integer(),
            sa.ForeignKey("announcements.id"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            nullable=False,
        ),
        sa.Column("dismiss_token", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "announcement_id",
            "author_id",
            "dismiss_token",
            name="unique_dismissal",
        ),
    )
    op.create_index(
        "ix_announcement_dismissals_announcement_id",
        "announcement_dismissals",
        ["announcement_id"],
    )
    op.create_index(
        "ix_announcement_dismissals_author_id",
        "announcement_dismissals",
        ["author_id"],
    )

    # ----- inbox_messages -------------------------------------------------
    op.create_table(
        "inbox_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "recipient_id",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="unread"
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("dedup_key", sa.String(length=200), nullable=False),
        sa.Column(
            "related_comment_id",
            sa.Integer(),
            sa.ForeignKey("plugin_comments.id"),
            nullable=True,
        ),
        sa.Column(
            "related_plugin_id",
            sa.String(length=120),
            sa.ForeignKey("plugins.plugin_id"),
            nullable=True,
        ),
        sa.Column(
            "related_announcement_id",
            sa.Integer(),
            sa.ForeignKey("announcements.id"),
            nullable=True,
        ),
        sa.Column(
            "source_author_id",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("recipient_id", "dedup_key", name="unique_inbox_dedup"),
    )
    op.create_index("ix_inbox_messages_recipient_id", "inbox_messages", ["recipient_id"])
    op.create_index("ix_inbox_messages_type", "inbox_messages", ["type"])
    op.create_index(
        "idx_inbox_recipient_status_created",
        "inbox_messages",
        ["recipient_id", "status", "created_at"],
    )

    # ----- comment_mentions ----------------------------------------------
    op.create_table(
        "comment_mentions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "comment_id",
            sa.Integer(),
            sa.ForeignKey("plugin_comments.id"),
            nullable=False,
        ),
        sa.Column(
            "mentioned_author_id",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "comment_id",
            "mentioned_author_id",
            name="unique_comment_mention",
        ),
    )
    op.create_index("ix_comment_mentions_comment_id", "comment_mentions", ["comment_id"])
    op.create_index(
        "idx_mentions_mentioned",
        "comment_mentions",
        ["mentioned_author_id", "created_at"],
    )

    # ----- plugin_metadata_changes ---------------------------------------
    op.create_table(
        "plugin_metadata_changes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "plugin_id",
            sa.String(length=120),
            sa.ForeignKey("plugins.plugin_id"),
            nullable=False,
        ),
        sa.Column(
            "operator_id",
            sa.String(length=120),
            sa.ForeignKey("authors.author_id"),
            nullable=False,
        ),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_plugin_metadata_changes_plugin_id",
        "plugin_metadata_changes",
        ["plugin_id"],
    )
    op.create_index(
        "ix_plugin_metadata_changes_operator_id",
        "plugin_metadata_changes",
        ["operator_id"],
    )
    op.create_index(
        "ix_plugin_metadata_changes_created_at",
        "plugin_metadata_changes",
        ["created_at"],
    )

    # ----- plugin_comments.mention_payload + composite index --------------
    with op.batch_alter_table("plugin_comments") as batch_op:
        batch_op.add_column(sa.Column("mention_payload", sa.JSON(), nullable=True))
    op.create_index(
        "idx_comments_plugin_parent_created",
        "plugin_comments",
        ["plugin_id", "parent_id", "created_at"],
    )

    # ----- additional plugins indexes -------------------------------------
    op.create_index(
        "idx_plugins_status_trust",
        "plugins",
        ["status", "trust_level"],
    )
    op.create_index(
        "idx_plugins_updated_at",
        "plugins",
        ["updated_at"],
    )


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    """Reverse all phase-1 schema additions."""

    op.drop_index("idx_plugins_updated_at", table_name="plugins")
    op.drop_index("idx_plugins_status_trust", table_name="plugins")

    op.drop_index(
        "idx_comments_plugin_parent_created",
        table_name="plugin_comments",
    )
    with op.batch_alter_table("plugin_comments") as batch_op:
        batch_op.drop_column("mention_payload")

    op.drop_index(
        "ix_plugin_metadata_changes_created_at",
        table_name="plugin_metadata_changes",
    )
    op.drop_index(
        "ix_plugin_metadata_changes_operator_id",
        table_name="plugin_metadata_changes",
    )
    op.drop_index(
        "ix_plugin_metadata_changes_plugin_id",
        table_name="plugin_metadata_changes",
    )
    op.drop_table("plugin_metadata_changes")

    op.drop_index("idx_mentions_mentioned", table_name="comment_mentions")
    op.drop_index("ix_comment_mentions_comment_id", table_name="comment_mentions")
    op.drop_table("comment_mentions")

    op.drop_index(
        "idx_inbox_recipient_status_created",
        table_name="inbox_messages",
    )
    op.drop_index("ix_inbox_messages_type", table_name="inbox_messages")
    op.drop_index("ix_inbox_messages_recipient_id", table_name="inbox_messages")
    op.drop_table("inbox_messages")

    op.drop_index(
        "ix_announcement_dismissals_author_id",
        table_name="announcement_dismissals",
    )
    op.drop_index(
        "ix_announcement_dismissals_announcement_id",
        table_name="announcement_dismissals",
    )
    op.drop_table("announcement_dismissals")
    op.drop_table("announcements")

    op.drop_index("idx_curation_enabled_sort", table_name="curation_entries")
    op.drop_index("ix_curation_entries_slot_type", table_name="curation_entries")
    op.drop_table("curation_entries")

    op.drop_index("idx_pinned_author", table_name="pinned_plugins")
    op.drop_index("ix_pinned_plugins_plugin_id", table_name="pinned_plugins")
    op.drop_index("ix_pinned_plugins_author_id", table_name="pinned_plugins")
    op.drop_table("pinned_plugins")

    op.drop_table("author_profiles")

    # NOTE: PostgreSQL does not support removing values from an enum type.
    # The new ``reviewaction`` values added in upgrade() are intentionally
    # left in place during downgrade; they are unused but harmless. Restoring
    # the previous enum requires a manual ``CREATE TYPE / ALTER TABLE / DROP
    # TYPE`` rewrite that is out of scope for an automated downgrade.
