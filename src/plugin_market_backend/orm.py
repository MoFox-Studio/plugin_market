"""SQLAlchemy ORM models for the plugin market backend."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from plugin_market_backend.enums import AuthorType, PluginStatus, ReviewAction, SyncStatus, TrustLevel, VersionStatus


def utc_now() -> datetime:
    """Return the current UTC datetime."""

    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class AuthorORM(Base):
    """Author or organization identity bound to GitHub."""

    __tablename__ = "authors"

    author_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    github_user_id: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    github_login: Mapped[str] = mapped_column(String(120), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    avatar_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    author_type: Mapped[AuthorType] = mapped_column(SAEnum(AuthorType), default=AuthorType.USER)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    owned_plugins: Mapped[list[PluginORM]] = relationship(back_populates="owner")


class AuthSessionORM(Base):
    """Browser session created from GitHub OAuth."""

    __tablename__ = "auth_sessions"

    session_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class OAuthStateORM(Base):
    """One-time OAuth state value for CSRF protection."""

    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(String(160), primary_key=True)
    redirect_to: Mapped[str] = mapped_column(String(1000), default="/")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PluginORM(Base):
    """Market plugin record."""

    __tablename__ = "plugins"
    __table_args__ = (
        Index("idx_plugins_status_trust", "status", "trust_level"),
        Index("idx_plugins_updated_at", "updated_at"),
    )

    plugin_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    readme_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    plugin_dependencies: Mapped[list[str]] = mapped_column(JSON, default=list)
    icon_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    homepage: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    repository_url: Mapped[str] = mapped_column(String(1000))
    license: Mapped[str] = mapped_column(String(120))
    categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[PluginStatus] = mapped_column(SAEnum(PluginStatus), default=PluginStatus.PENDING_REVIEW, index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    trust_level: Mapped[TrustLevel] = mapped_column(SAEnum(TrustLevel), default=TrustLevel.COMMUNITY)
    risk_notice: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    owner: Mapped[AuthorORM] = relationship(back_populates="owned_plugins")
    versions: Mapped[list[PluginVersionORM]] = relationship(back_populates="plugin", cascade="all, delete-orphan")
    maintainers: Mapped[list[PluginMaintainerORM]] = relationship(back_populates="plugin", cascade="all, delete-orphan")


class PluginMaintainerORM(Base):
    """Plugin maintainer mapping."""

    __tablename__ = "plugin_maintainers"
    __table_args__ = (UniqueConstraint("plugin_id", "author_id", name="uq_plugin_maintainer"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugins.plugin_id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    plugin: Mapped[PluginORM] = relationship(back_populates="maintainers")


class PluginVersionORM(Base):
    """Installable plugin version indexed by the market."""

    __tablename__ = "plugin_versions"
    __table_args__ = (UniqueConstraint("plugin_id", "version", name="uq_plugin_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugins.plugin_id"), index=True)
    version: Mapped[str] = mapped_column(String(80), index=True)
    release_tag: Mapped[str] = mapped_column(String(120))
    release_title: Mapped[str] = mapped_column(String(300))
    release_url: Mapped[str] = mapped_column(String(1000))
    asset_name: Mapped[str] = mapped_column(String(300))
    asset_download_url: Mapped[str] = mapped_column(String(1000))
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    file_size: Mapped[int] = mapped_column(Integer)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    is_prerelease: Mapped[bool] = mapped_column(Boolean, default=False)
    is_yanked: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[VersionStatus] = mapped_column(SAEnum(VersionStatus), default=VersionStatus.PENDING_REVIEW, index=True)
    plugin_api_version: Mapped[str] = mapped_column(String(80))
    min_host_version: Mapped[str] = mapped_column(String(80))
    max_host_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    supported_platforms: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["all"])
    last_sync_status: Mapped[SyncStatus] = mapped_column(SAEnum(SyncStatus), default=SyncStatus.NONE)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    plugin: Mapped[PluginORM] = relationship(back_populates="versions")


class PluginLikeORM(Base):
    """Like relationship between an author and a plugin."""

    __tablename__ = "plugin_likes"
    __table_args__ = (UniqueConstraint("plugin_id", "author_id", name="uq_plugin_like"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugins.plugin_id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PluginRatingORM(Base):
    """User rating (1-5) for a plugin."""

    __tablename__ = "plugin_ratings"
    __table_args__ = (UniqueConstraint("plugin_id", "author_id", name="uq_plugin_rating"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugins.plugin_id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class PluginCommentORM(Base):
    """Threaded comment on a plugin."""

    __tablename__ = "plugin_comments"
    __table_args__ = (
        Index(
            "idx_comments_plugin_parent_created",
            "plugin_id",
            "parent_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugins.plugin_id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("plugin_comments.id"), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text)
    mention_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ReviewRecordORM(Base):
    """Persistent audit record for review and governance operations."""

    __tablename__ = "review_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_type: Mapped[str] = mapped_column(String(40), index=True)
    target_id: Mapped[str] = mapped_column(String(240), index=True)
    action: Mapped[ReviewAction] = mapped_column(SAEnum(ReviewAction), index=True)
    status_before: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status_after: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator_id: Mapped[str] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class WebhookEventORM(Base):
    """Stored GitHub webhook event for deduplication and audit."""

    __tablename__ = "webhook_events"

    event_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    event_name: Mapped[str] = mapped_column(String(80), index=True)
    action: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    accepted: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


# ---------------------------------------------------------------------------
# plugin-market-overhaul phase 1 (migration 0004)
# ---------------------------------------------------------------------------


class AuthorProfileORM(Base):
    """Per-author personal-space profile (1:1 with ``authors``)."""

    __tablename__ = "author_profiles"

    author_id: Mapped[str] = mapped_column(
        String(120),
        ForeignKey("authors.author_id"),
        primary_key=True,
    )
    bio: Mapped[str] = mapped_column(Text, default="", server_default="")
    background_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    background_image_kind: Mapped[str] = mapped_column(
        String(16),
        default="url",
        server_default="url",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class PinnedPluginORM(Base):
    """Author-curated pin slot pointing at one of their plugins."""

    __tablename__ = "pinned_plugins"
    __table_args__ = (
        UniqueConstraint("author_id", "plugin_id", name="unique_pinned"),
        Index("idx_pinned_author", "author_id", "pinned_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    author_id: Mapped[str] = mapped_column(
        ForeignKey("authors.author_id"), nullable=False, index=True
    )
    plugin_id: Mapped[str] = mapped_column(
        ForeignKey("plugins.plugin_id"), nullable=False, index=True
    )
    pinned_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pinned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class CurationEntryORM(Base):
    """Operations-managed showcase / featured entry."""

    __tablename__ = "curation_entries"
    __table_args__ = (Index("idx_curation_enabled_sort", "enabled", "sort_order"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[str] = mapped_column(String(240), nullable=False)
    signature_plugin_id: Mapped[str | None] = mapped_column(
        ForeignKey("plugins.plugin_id"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    audience: Mapped[str] = mapped_column(
        String(40), default="all", server_default="all", nullable=False
    )
    display_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(
        ForeignKey("authors.author_id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class AnnouncementORM(Base):
    """Site-wide announcement (banner or modal)."""

    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, default="", server_default="")
    display_mode: Mapped[str] = mapped_column(
        String(20), default="banner", server_default="banner", nullable=False
    )
    severity: Mapped[str] = mapped_column(
        String(20), default="info", server_default="info", nullable=False
    )
    dismissible: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    audience: Mapped[str] = mapped_column(
        String(40), default="all", server_default="all", nullable=False
    )
    emit_inbox: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    dismiss_token: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    created_by: Mapped[str] = mapped_column(
        ForeignKey("authors.author_id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class AnnouncementDismissalORM(Base):
    """Per-viewer dismissal records for announcements."""

    __tablename__ = "announcement_dismissals"
    __table_args__ = (
        UniqueConstraint(
            "announcement_id",
            "author_id",
            "dismiss_token",
            name="unique_dismissal",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    announcement_id: Mapped[int] = mapped_column(
        ForeignKey("announcements.id"), nullable=False, index=True
    )
    author_id: Mapped[str] = mapped_column(
        ForeignKey("authors.author_id"), nullable=False, index=True
    )
    dismiss_token: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class InboxMessageORM(Base):
    """Derived per-recipient inbox message."""

    __tablename__ = "inbox_messages"
    __table_args__ = (
        Index(
            "idx_inbox_recipient_status_created",
            "recipient_id",
            "status",
            "created_at",
        ),
        UniqueConstraint("recipient_id", "dedup_key", name="unique_inbox_dedup"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_id: Mapped[str] = mapped_column(
        ForeignKey("authors.author_id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16), default="unread", server_default="unread", nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    dedup_key: Mapped[str] = mapped_column(String(200), nullable=False)
    related_comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("plugin_comments.id"), nullable=True
    )
    related_plugin_id: Mapped[str | None] = mapped_column(
        ForeignKey("plugins.plugin_id"), nullable=True
    )
    related_announcement_id: Mapped[int | None] = mapped_column(
        ForeignKey("announcements.id"), nullable=True
    )
    source_author_id: Mapped[str | None] = mapped_column(
        ForeignKey("authors.author_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CommentMentionORM(Base):
    """Normalized record of an ``@<login>`` mention in a comment."""

    __tablename__ = "comment_mentions"
    __table_args__ = (
        UniqueConstraint(
            "comment_id",
            "mentioned_author_id",
            name="unique_comment_mention",
        ),
        Index(
            "idx_mentions_mentioned",
            "mentioned_author_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("plugin_comments.id"), nullable=False, index=True
    )
    mentioned_author_id: Mapped[str] = mapped_column(
        ForeignKey("authors.author_id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class PluginMetadataChangeORM(Base):
    """Audit log entry for inline plugin metadata edits."""

    __tablename__ = "plugin_metadata_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(
        ForeignKey("plugins.plugin_id"), nullable=False, index=True
    )
    operator_id: Mapped[str] = mapped_column(
        ForeignKey("authors.author_id"), nullable=False, index=True
    )
    changed_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
