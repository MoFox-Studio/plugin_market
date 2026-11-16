"""插件市场后端的 SQLAlchemy ORM 模型。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from plugin_market_backend.enums import AuthorType, PluginStatus, ReviewAction, SkillStatus, SyncStatus, TrustLevel, VersionStatus


def utc_now() -> datetime:
    """返回当前 UTC 日期时间。"""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


class AuthorORM(Base):
    """绑定 GitHub 的作者或组织身份。"""

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
    """通过 GitHub OAuth 创建的浏览器会话。"""

    __tablename__ = "auth_sessions"

    session_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class OAuthStateORM(Base):
    """用于 CSRF 防护的一次性 OAuth state 值。"""

    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(String(160), primary_key=True)
    redirect_to: Mapped[str] = mapped_column(String(1000), default="/")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PluginORM(Base):
    """市场插件记录。"""

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
    """插件与维护者的关联记录。"""

    __tablename__ = "plugin_maintainers"
    __table_args__ = (UniqueConstraint("plugin_id", "author_id", name="uq_plugin_maintainer"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugins.plugin_id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    plugin: Mapped[PluginORM] = relationship(back_populates="maintainers")


class PluginVersionORM(Base):
    """由市场索引的可安装插件版本。"""

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
    """作者与插件之间的点赞关系。"""

    __tablename__ = "plugin_likes"
    __table_args__ = (UniqueConstraint("plugin_id", "author_id", name="uq_plugin_like"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugins.plugin_id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RecommendationPreferenceORM(Base):
    """显式推荐设置，不包含浏览历史或推断身份。"""

    __tablename__ = "recommendation_preferences"

    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), primary_key=True)
    personalization_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RecommendationFeedbackORM(Base):
    """按作者隔离、有过期时间的显式排除项与分类降权设置。"""

    __tablename__ = "recommendation_feedback"
    __table_args__ = (Index("idx_recommendation_feedback_expiry", "expires_at"),)

    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), primary_key=True)
    target: Mapped[str] = mapped_column(String(120), primary_key=True)
    reason: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=False)


class AuthorFollowORM(Base):
    """浏览者与插件作者之间的关注关系。"""

    __tablename__ = "author_follows"
    __table_args__ = (
        UniqueConstraint("follower_id", "author_id", name="uq_author_follow"),
        Index("idx_author_follows_author_created", "author_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    follower_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PluginSubscriptionORM(Base):
    """作者与插件之间的订阅关系。"""

    __tablename__ = "plugin_subscriptions"
    __table_args__ = (
        UniqueConstraint("plugin_id", "author_id", name="uq_plugin_subscription"),
        Index("idx_plugin_subscriptions_plugin_created", "plugin_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugins.plugin_id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuthorAccessTokenORM(Base):
    """市场作者持有的唯一有效机器访问令牌。"""

    __tablename__ = "author_access_tokens"

    author_id: Mapped[str] = mapped_column(
        ForeignKey("authors.author_id"),
        primary_key=True,
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    token_preview: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PluginRatingORM(Base):
    """用户对插件的评分（1 至 5 分）。"""

    __tablename__ = "plugin_ratings"
    __table_args__ = (UniqueConstraint("plugin_id", "author_id", name="uq_plugin_rating"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugins.plugin_id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class PluginCommentORM(Base):
    """插件的嵌套评论。"""

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
    """审核与治理操作的持久化审计记录。"""

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
    """为去重与审计存储的 GitHub Webhook 事件。"""

    __tablename__ = "webhook_events"

    event_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    event_name: Mapped[str] = mapped_column(String(80), index=True)
    action: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    accepted: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


# ---------------------------------------------------------------------------
# 插件市场改版第一阶段（迁移 0004）
# ---------------------------------------------------------------------------


class AuthorProfileORM(Base):
    """作者的个人空间资料，与 ``authors`` 一一对应。"""

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
    """由作者选定、指向其某个插件的置顶条目。"""

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
    """由运营管理的展示或精选条目。"""

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
    """全站公告（横幅或弹窗）。"""

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
    """按浏览者保存的公告关闭记录。"""

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
    """为每个接收者派生的收件箱消息。"""

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
    """评论中 ``@<login>`` 提及的规范化记录。"""

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
    """插件元数据行内编辑的审计日志条目。"""

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


# ---------------------------------------------------------------------------
# 技能市场（迁移 0006）
# ---------------------------------------------------------------------------


class SkillORM(Base):
    """市场技能记录。"""

    __tablename__ = "skills"
    __table_args__ = (
        Index("idx_skills_status_trust", "status", "trust_level"),
        Index("idx_skills_updated_at", "updated_at"),
    )

    skill_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    readme_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    icon_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[SkillStatus] = mapped_column(SAEnum(SkillStatus, native_enum=False), default=SkillStatus.PUBLISHED, index=True)
    trust_level: Mapped[TrustLevel] = mapped_column(SAEnum(TrustLevel), default=TrustLevel.COMMUNITY)
    download_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    owner: Mapped[AuthorORM] = relationship()
    versions: Mapped[list[SkillVersionORM]] = relationship(back_populates="skill", cascade="all, delete-orphan")


class SkillVersionORM(Base):
    """可安装的技能版本（ZIP 包）。"""

    __tablename__ = "skill_versions"
    __table_args__ = (
        UniqueConstraint("skill_id", "version", name="uq_skill_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.skill_id"), index=True)
    version: Mapped[str] = mapped_column(String(80), index=True)
    package_path: Mapped[str] = mapped_column(String(500))
    package_size: Mapped[int] = mapped_column(Integer)
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    release_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    min_mofox_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    skill: Mapped[SkillORM] = relationship(back_populates="versions")


class SkillLikeORM(Base):
    """作者与技能之间的点赞关系。"""

    __tablename__ = "skill_likes"
    __table_args__ = (UniqueConstraint("skill_id", "author_id", name="uq_skill_like"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.skill_id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SkillRatingORM(Base):
    """用户对技能的评分（1 至 5 分）。"""

    __tablename__ = "skill_ratings"
    __table_args__ = (UniqueConstraint("skill_id", "author_id", name="uq_skill_rating"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.skill_id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class SkillCommentORM(Base):
    """技能的嵌套评论。"""

    __tablename__ = "skill_comments"
    __table_args__ = (
        Index(
            "idx_skill_comments_skill_parent_created",
            "skill_id",
            "parent_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.skill_id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("skill_comments.id"), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text)
    mention_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class SkillSubscriptionORM(Base):
    """作者与技能之间的订阅关系。"""

    __tablename__ = "skill_subscriptions"
    __table_args__ = (
        UniqueConstraint("skill_id", "author_id", name="uq_skill_subscription"),
        Index("idx_skill_subscriptions_skill_created", "skill_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.skill_id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.author_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
