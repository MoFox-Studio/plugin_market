"""SQLAlchemy ORM models for the plugin market backend."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugins.plugin_id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("plugin_comments.id"), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text)
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
