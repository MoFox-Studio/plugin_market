"""Initial plugin market schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


author_type = sa.Enum("USER", "ORGANIZATION", name="authortype")
plugin_status = sa.Enum("DRAFT", "PENDING_REVIEW", "PUBLISHED", "DEPRECATED", "BLOCKED", "ARCHIVED", name="pluginstatus")
trust_level = sa.Enum("OFFICIAL", "VERIFIED", "COMMUNITY", name="trustlevel")
version_status = sa.Enum("SUBMITTED", "PENDING_REVIEW", "PUBLISHED", "YANKED", "BLOCKED", name="versionstatus")
sync_status = sa.Enum("NONE", "SUCCESS", "FAILED", name="syncstatus")
review_action = sa.Enum(
    "REGISTER_PLUGIN",
    "UPDATE_PLUGIN",
    "SUBMIT_VERSION",
    "APPROVE_PLUGIN",
    "REJECT_PLUGIN",
    "BLOCK_PLUGIN",
    "DEPRECATE_PLUGIN",
    "ARCHIVE_PLUGIN",
    "APPROVE_VERSION",
    "REJECT_VERSION",
    "YANK_VERSION",
    "BLOCK_VERSION",
    "SYNC_VERSION",
    "WEBHOOK_RECEIVED",
    "MAINTAINER_ADD",
    "MAINTAINER_REMOVE",
    name="reviewaction",
)


def upgrade() -> None:
    """Apply initial schema."""

    op.create_table(
        "authors",
        sa.Column("author_id", sa.String(length=120), primary_key=True),
        sa.Column("github_user_id", sa.String(length=120), nullable=True, unique=True),
        sa.Column("github_login", sa.String(length=120), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("avatar_url", sa.String(length=1000), nullable=True),
        sa.Column("author_type", author_type, nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "plugins",
        sa.Column("plugin_id", sa.String(length=120), primary_key=True),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("icon_url", sa.String(length=1000), nullable=True),
        sa.Column("homepage", sa.String(length=1000), nullable=True),
        sa.Column("repository_url", sa.String(length=1000), nullable=False),
        sa.Column("license", sa.String(length=120), nullable=False),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("status", plugin_status, nullable=False),
        sa.Column("owner_id", sa.String(length=120), sa.ForeignKey("authors.author_id"), nullable=False),
        sa.Column("trust_level", trust_level, nullable=False),
        sa.Column("risk_notice", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_plugins_owner_id", "plugins", ["owner_id"])
    op.create_index("ix_plugins_status", "plugins", ["status"])
    op.create_table(
        "plugin_maintainers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plugin_id", sa.String(length=120), sa.ForeignKey("plugins.plugin_id"), nullable=False),
        sa.Column("author_id", sa.String(length=120), sa.ForeignKey("authors.author_id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("plugin_id", "author_id", name="uq_plugin_maintainer"),
    )
    op.create_index("ix_plugin_maintainers_author_id", "plugin_maintainers", ["author_id"])
    op.create_index("ix_plugin_maintainers_plugin_id", "plugin_maintainers", ["plugin_id"])
    op.create_table(
        "plugin_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plugin_id", sa.String(length=120), sa.ForeignKey("plugins.plugin_id"), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("release_tag", sa.String(length=120), nullable=False),
        sa.Column("release_title", sa.String(length=300), nullable=False),
        sa.Column("release_url", sa.String(length=1000), nullable=False),
        sa.Column("asset_name", sa.String(length=300), nullable=False),
        sa.Column("asset_download_url", sa.String(length=1000), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_prerelease", sa.Boolean(), nullable=False),
        sa.Column("is_yanked", sa.Boolean(), nullable=False),
        sa.Column("status", version_status, nullable=False),
        sa.Column("plugin_api_version", sa.String(length=80), nullable=False),
        sa.Column("min_host_version", sa.String(length=80), nullable=False),
        sa.Column("max_host_version", sa.String(length=80), nullable=True),
        sa.Column("supported_platforms", sa.JSON(), nullable=False),
        sa.Column("last_sync_status", sync_status, nullable=False),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("plugin_id", "version", name="uq_plugin_version"),
    )
    op.create_index("ix_plugin_versions_plugin_id", "plugin_versions", ["plugin_id"])
    op.create_index("ix_plugin_versions_published_at", "plugin_versions", ["published_at"])
    op.create_index("ix_plugin_versions_status", "plugin_versions", ["status"])
    op.create_index("ix_plugin_versions_version", "plugin_versions", ["version"])
    op.create_table(
        "review_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=240), nullable=False),
        sa.Column("action", review_action, nullable=False),
        sa.Column("status_before", sa.String(length=80), nullable=True),
        sa.Column("status_after", sa.String(length=80), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("operator_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_review_records_action", "review_records", ["action"])
    op.create_index("ix_review_records_created_at", "review_records", ["created_at"])
    op.create_index("ix_review_records_operator_id", "review_records", ["operator_id"])
    op.create_index("ix_review_records_target_id", "review_records", ["target_id"])
    op.create_index("ix_review_records_target_type", "review_records", ["target_type"])
    op.create_table(
        "webhook_events",
        sa.Column("event_id", sa.String(length=160), primary_key=True),
        sa.Column("event_name", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_webhook_events_created_at", "webhook_events", ["created_at"])
    op.create_index("ix_webhook_events_event_name", "webhook_events", ["event_name"])


def downgrade() -> None:
    """Drop initial schema."""

    op.drop_index("ix_webhook_events_event_name", table_name="webhook_events")
    op.drop_index("ix_webhook_events_created_at", table_name="webhook_events")
    op.drop_table("webhook_events")
    op.drop_index("ix_review_records_target_type", table_name="review_records")
    op.drop_index("ix_review_records_target_id", table_name="review_records")
    op.drop_index("ix_review_records_operator_id", table_name="review_records")
    op.drop_index("ix_review_records_created_at", table_name="review_records")
    op.drop_index("ix_review_records_action", table_name="review_records")
    op.drop_table("review_records")
    op.drop_index("ix_plugin_versions_version", table_name="plugin_versions")
    op.drop_index("ix_plugin_versions_status", table_name="plugin_versions")
    op.drop_index("ix_plugin_versions_published_at", table_name="plugin_versions")
    op.drop_index("ix_plugin_versions_plugin_id", table_name="plugin_versions")
    op.drop_table("plugin_versions")
    op.drop_index("ix_plugin_maintainers_plugin_id", table_name="plugin_maintainers")
    op.drop_index("ix_plugin_maintainers_author_id", table_name="plugin_maintainers")
    op.drop_table("plugin_maintainers")
    op.drop_index("ix_plugins_status", table_name="plugins")
    op.drop_index("ix_plugins_owner_id", table_name="plugins")
    op.drop_table("plugins")
    op.drop_table("authors")
