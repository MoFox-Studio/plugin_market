"""插件市场 API 的 Pydantic 数据模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

from plugin_market_backend.enums import AuthorType, PluginStatus, ReviewAction, SyncStatus, TrustLevel, VersionStatus


def _validate_sha256(value: str) -> str:
    """验证 SHA-256 十六进制字符串。

    Args:
        value: 待校验的校验和。

    Returns:
        转换为小写的校验和。

    Raises:
        ValueError: 校验和不是 64 个字符的十六进制字符串。
    """
    if len(value) != 64 or any(char not in "0123456789abcdefABCDEF" for char in value):
        raise ValueError("checksum_sha256 必须是 64 个字符的十六进制字符串")
    return value.lower()


class Author(BaseModel):
    """作者身份信息响应。"""

    author_id: str
    github_user_id: str | None = None
    github_login: str
    display_name: str
    avatar_url: str | None = None
    author_type: AuthorType
    verified_at: datetime | None = None
    is_admin: bool = False


class AuthStatus(BaseModel):
    """当前浏览器或 API 的认证状态。"""

    authenticated: bool
    user: Author | None = None


class AuthorFollowState(BaseModel):
    """作者的关注开关状态。"""

    author_id: str
    following: bool
    followers_count: int


class PluginSubscriptionState(BaseModel):
    """插件的订阅开关状态。"""

    plugin_id: str
    subscribed: bool
    subscriptions_count: int


class AccessTokenStatus(BaseModel):
    """描述作者唯一有效访问令牌的元数据。"""

    author_id: str
    has_token: bool
    token_preview: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_used_at: datetime | None = None


class AccessTokenRotateResponse(BaseModel):
    """仅在创建或轮换时返回的明文令牌。"""

    author_id: str
    token: str
    token_preview: str
    created_at: datetime
    updated_at: datetime


class MachineSubscriptionItem(BaseModel):
    """返回给机器客户端的单个已订阅插件。"""

    plugin_id: str
    display_name: str | None = None
    latest_version: str | None = None
    updated_at: datetime | None = None


class MachineSubscriptionListResponse(BaseModel):
    """返回给机器客户端的已订阅插件列表。"""

    author_id: str
    items: list[MachineSubscriptionItem] = Field(default_factory=list)
    total: int = Field(ge=0)


class MySubscriptionItem(BaseModel):
    """当前用户订阅列表中的单个插件。"""

    plugin_id: str
    display_name: str
    summary: str
    icon_url: str | None = None
    status: PluginStatus
    owner_id: str
    owner_login: str | None = None
    owner_display_name: str | None = None
    latest_version: str | None = None
    updated_at: datetime | None = None
    subscribed_at: datetime


class MySubscriptionListResponse(BaseModel):
    """当前用户的已订阅插件列表。"""

    author_id: str
    items: list[MySubscriptionItem] = Field(default_factory=list)
    total: int = Field(ge=0)


class MyFollowItem(BaseModel):
    """当前用户关注列表中的单个作者。"""

    author_id: str
    github_login: str
    display_name: str
    avatar_url: str | None = None
    author_type: AuthorType
    followed_at: datetime


class MyFollowListResponse(BaseModel):
    """当前用户的已关注作者列表。"""

    author_id: str
    items: list[MyFollowItem] = Field(default_factory=list)
    total: int = Field(ge=0)


class PluginCreate(BaseModel):
    """注册插件的请求体。"""

    plugin_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_\-]*$")
    display_name: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    description: str = Field(default="")
    icon_url: HttpUrl | None = None
    icon_png_base64: str | None = None
    homepage: HttpUrl | None = None
    repository_url: HttpUrl
    license: str = Field(min_length=1)
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    maintainers: list[str] = Field(default_factory=list)
    plugin_dependencies: list[str] = Field(default_factory=list)
    readme_markdown: str | None = None


class PluginUpdate(BaseModel):
    """更新插件可变元数据的请求体。"""

    display_name: str | None = Field(default=None, min_length=1)
    summary: str | None = Field(default=None, min_length=1)
    description: str | None = None
    icon_url: HttpUrl | None = None
    icon_png_base64: str | None = None
    homepage: HttpUrl | None = None
    repository_url: HttpUrl | None = None
    license: str | None = Field(default=None, min_length=1)
    categories: list[str] | None = None
    tags: list[str] | None = None
    maintainers: list[str] | None = None
    plugin_dependencies: list[str] | None = None
    readme_markdown: str | None = None


class PluginDependency(BaseModel):
    """供详情视图使用的已解析插件依赖。"""

    plugin_id: str
    raw: str
    version_spec: str | None = None
    exists_in_market: bool = False
    display_name: str | None = None
    icon_url: str | None = None


class Plugin(BaseModel):
    """市场插件记录。"""

    plugin_id: str
    display_name: str
    summary: str
    description: str
    icon_url: str | None = None
    has_readme: bool = False
    homepage: str | None = None
    repository_url: str
    license: str
    categories: list[str]
    tags: list[str]
    status: PluginStatus
    owner_id: str
    owner_login: str | None = None
    owner_display_name: str | None = None
    owner_avatar_url: str | None = None
    maintainers: list[str]
    trust_level: TrustLevel
    risk_notice: str | None = None
    created_at: datetime
    updated_at: datetime
    likes_count: int = 0
    rating_avg: float = 0.0
    rating_count: int = 0
    comments_count: int = 0
    downloads_count: int = 0
    latest_version: str | None = None
    latest_version_published_at: datetime | None = None
    viewer_has_liked: bool = False
    viewer_rating: int | None = None


class PluginVersionCreate(BaseModel):
    """提交插件版本的请求体。"""

    version: str = Field(min_length=1)
    release_tag: str = Field(min_length=1)
    release_title: str = Field(min_length=1)
    release_url: HttpUrl
    asset_name: str = Field(min_length=1)
    asset_download_url: HttpUrl
    checksum_sha256: str
    file_size: int = Field(ge=0)
    is_prerelease: bool = False
    plugin_api_version: str = Field(min_length=1)
    min_host_version: str = Field(min_length=1)
    max_host_version: str | None = None
    supported_platforms: list[str] = Field(default_factory=lambda: ["all"])
    readme_markdown: str | None = None

    @field_validator("checksum_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        """要求 SHA-256 校验和为 64 个十六进制字符。

        Args:
            value: 待校验的校验和。

        Returns:
            转换为小写的校验和。

        Raises:
            ValueError: 校验和不是 64 个字符的十六进制字符串。
        """
        return _validate_sha256(value)


class PluginVersion(BaseModel):
    """市场插件版本记录。"""

    plugin_id: str
    version: str
    release_tag: str
    release_title: str
    release_url: str
    asset_name: str
    asset_download_url: str
    checksum_sha256: str
    file_size: int
    published_at: datetime
    is_prerelease: bool
    is_yanked: bool
    status: VersionStatus
    plugin_api_version: str
    min_host_version: str
    max_host_version: str | None
    supported_platforms: list[str]
    last_sync_status: SyncStatus = SyncStatus.NONE
    last_sync_error: str | None = None
    download_count: int = 0


class VersionSyncRequest(BaseModel):
    """通过 CLI 同步更新版本的请求体。"""

    version: str = Field(min_length=1)
    release_tag: str | None = None
    release_title: str | None = None
    release_url: HttpUrl | None = None
    asset_name: str | None = None
    asset_download_url: HttpUrl | None = None
    checksum_sha256: str | None = None
    file_size: int | None = Field(default=None, ge=0)

    @field_validator("checksum_sha256")
    @classmethod
    def validate_optional_sha256(cls, value: str | None) -> str | None:
        """校验可选的 SHA-256 校验和。

        Args:
            value: 待校验的校验和，未提供时为 None。

        Returns:
            转换为小写的校验和；未提供时返回 None。

        Raises:
            ValueError: 已提供的校验和不是 64 个字符的十六进制字符串。
        """
        return _validate_sha256(value) if value is not None else None


class VersionStatusItem(BaseModel):
    """返回给 CLI 的精简版本状态。"""

    version: str
    status: VersionStatus
    is_yanked: bool
    last_sync_status: SyncStatus
    last_sync_error: str | None


class PluginStatusResponse(BaseModel):
    """返回给 CLI 的插件状态响应。"""

    plugin_id: str
    plugin_status: PluginStatus
    versions: list[VersionStatusItem]


class InstallInfo(BaseModel):
    """返回给客户端和 CLI 的安装元数据。"""

    plugin: Plugin
    version: PluginVersion


class MarketStats(BaseModel):
    """管理员统计信息响应。"""

    plugins_total: int
    versions_total: int
    comments_total: int = 0
    ratings_total: int = 0
    likes_total: int = 0
    downloads_total: int = 0
    pending_plugins: int
    pending_versions: int
    published_plugins: int = 0
    blocked_plugins: int = 0
    deprecated_plugins: int = 0
    archived_plugins: int = 0
    authors_total: int = 0
    webhooks_total: int = 0
    latest_review_at: datetime | None = None


class ReviewRecord(BaseModel):
    """审核与同步操作的审计记录。"""

    target_type: str
    target_id: str
    action: ReviewAction
    status_before: str | None = None
    status_after: str | None = None
    reason: str | None = None
    operator_id: str
    created_at: datetime


class ReviewDecision(BaseModel):
    """管理员审核请求体。"""

    reason: str | None = None


class PluginListResponse(BaseModel):
    """分页插件列表响应。"""

    items: list[Plugin]
    total: int


class VersionListResponse(BaseModel):
    """插件版本列表响应。"""

    items: list[PluginVersion]
    total: int


class TaxonomyResponse(BaseModel):
    """分类或标签响应。"""

    items: list[str]


class WebhookResponse(BaseModel):
    """接收 GitHub Webhook 的响应。"""

    accepted: bool
    event_id: str


class PluginReadmeResponse(BaseModel):
    """供插件详情页使用的已渲染 README 数据。"""

    plugin_id: str
    exists: bool
    html: str | None = None


class PluginDependenciesResponse(BaseModel):
    """供详情页使用的已解析插件依赖数据。"""

    plugin_id: str
    items: list[PluginDependency] = Field(default_factory=list)


class CommentAuthor(BaseModel):
    """随评论返回的精简作者信息。"""

    author_id: str
    github_login: str
    display_name: str
    avatar_url: str | None = None
    is_admin: bool = False


class MentionCandidate(BaseModel):
    """供搜索和评论渲染使用的已解析提及候选人。"""

    author_id: str
    github_login: str
    display_name: str
    avatar_url: str | None = None


class Comment(BaseModel):
    """用户对插件的评论。"""

    id: int
    plugin_id: str
    parent_id: int | None
    content: str
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False
    author: CommentAuthor
    mentions: list[MentionCandidate] = Field(default_factory=list)


class CommentCreate(BaseModel):
    """提交评论的请求体。"""

    content: str = Field(min_length=1, max_length=4000)
    parent_id: int | None = None


class CommentListResponse(BaseModel):
    """分页评论响应。"""

    items: list[Comment]
    total: int


class RatingRequest(BaseModel):
    """为插件评分的请求体。"""

    score: int = Field(ge=1, le=5)


class RatingSummary(BaseModel):
    """插件的评分汇总统计。"""

    plugin_id: str
    rating_avg: float
    rating_count: int
    distribution: dict[str, int] = Field(default_factory=dict)
    viewer_rating: int | None = None


class ActivityPoint(BaseModel):
    """管理仪表盘中的每日市场活动统计。"""

    date: str
    plugins_created: int = 0
    versions_created: int = 0
    comments_created: int = 0
    ratings_created: int = 0
    review_events: int = 0


class PluginGovernanceSnapshot(BaseModel):
    """供管理员和所有者视图使用的插件治理详细数据。"""

    plugin: Plugin
    versions: list[PluginVersion] = Field(default_factory=list)
    recent_reviews: list[ReviewRecord] = Field(default_factory=list)


class AdminDashboard(BaseModel):
    """管理仪表盘的汇总数据。"""

    stats: MarketStats
    plugin_status_breakdown: dict[str, int] = Field(default_factory=dict)
    version_status_breakdown: dict[str, int] = Field(default_factory=dict)
    activity: list[ActivityPoint] = Field(default_factory=list)
    popular_plugins: list[Plugin] = Field(default_factory=list)


class CommunitySnapshot(BaseModel):
    """供详情视图使用的社区汇总数据。"""

    plugin: Plugin
    rating: RatingSummary
    recent_comments: list[Comment] = Field(default_factory=list)


class TrendingItem(BaseModel):
    """轻量级热门作者或统计条目。"""

    author_id: str
    github_login: str
    display_name: str
    avatar_url: str | None = None
    bio: str | None = None
    plugins_count: int
    likes_received: int
    downloads_total: int
    rating_avg: float = 0.0
    rating_count: int = 0
    best_plugin: "TrendingPlugin | None" = None


class TrendingPlugin(BaseModel):
    """用作作者默认代表作的精简插件信息。"""

    plugin_id: str
    display_name: str
    summary: str
    icon_url: str | None = None
    latest_version: str | None = None


# ---------------------------------------------------------------------------
# 插件市场改版第一阶段（任务 2）：增量 Pydantic 数据模型
# ---------------------------------------------------------------------------


# 共享字面量取值 -------------------------------------------------

AudienceLiteral = Literal[
    "all",
    "logged_in",
    "anonymous",
    "admins",
    "authors_with_plugin",
]
"""精选条目与公告共用的受众选择条件。"""

DisplayModeLiteral = Literal["banner", "modal"]
"""公告展示方式。"""

SeverityLiteral = Literal["info", "warning", "critical"]
"""公告严重级别。"""

SlotTypeLiteral = Literal[
    "featured_plugin",
    "featured_author",
    "signature_plugin",
    "hero",
    "sidebar",
]
"""首页展示区中渲染的精选展示位类型。"""

TargetTypeLiteral = Literal["plugin", "author"]
"""精选条目引用的资源类型。"""

InboxMessageType = Literal[
    "mention",
    "reply",
    "governance",
    "announcement",
    "author_activity",
    "plugin_activity",
    "system",
]
"""收件箱消息类别。"""

InboxMessageStatus = Literal["unread", "read", "revoked"]
"""收件箱消息的生命周期状态。"""

InboxLinkKind = Literal["comment", "plugin", "announcement", "system"]
"""打开收件箱消息时的跳转目标。"""

BulkActionLiteral = Literal[
    "publish",
    "reject",
    "block",
    "deprecate",
    "set_trust_level",
    "delete",
]
"""接口 ``POST /api/v1/admin/plugins/bulk`` 接受的管理员批量操作。"""


# 字段级辅助函数 ---------------------------------------------------------


def _ensure_https(value: HttpUrl | None) -> HttpUrl | None:
    """拒绝敏感媒体引用中的非 HTTPS URL。

    Args:
        value: 待校验的媒体 URL，未提供时为 None。

    Returns:
        校验通过的原始 URL；未提供时返回 None。

    Raises:
        ValueError: URL 未使用 https 协议。
    """
    if value is None:
        return None
    if value.scheme != "https":
        raise ValueError("URL 必须使用 https 协议")
    return value


def _validate_tag_list(values: list[str]) -> list[str]:
    """校验标签总数和单个标签的长度限制。

    Args:
        values: 待校验的标签列表。

    Returns:
        校验通过的原始标签列表。

    Raises:
        ValueError: 标签超过 10 个，或存在非字符串、长度不在 1 至 40 之间的标签。
    """
    if len(values) > 10:
        raise ValueError("最多允许 10 个标签")
    for tag in values:
        if not isinstance(tag, str) or not (1 <= len(tag) <= 40):
            raise ValueError("每个标签必须包含 1 至 40 个字符")
    return values


# 作者资料与个人空间 --------------------------------------------


class AuthorProfile(BaseModel):
    """返回给市场前端的个人空间资料。"""

    author_id: str
    bio: str = Field(default="", max_length=2000)
    background_image_url: str | None = None
    background_image_kind: Literal["url", "upload"] = "url"
    updated_at: datetime | None = None


class AuthorProfileUpdate(BaseModel):
    """接口 ``PUT /api/v1/me/profile`` 的部分更新请求数据。"""

    bio: str | None = Field(default=None, max_length=2000)
    # 接受 HTTPS URL 或内部 /plugin-media/ 路径（已上传的图片），
    # 也接受空字符串，表示清除当前背景。
    background_image_url: str | None = None

    @field_validator("background_image_url")
    @classmethod
    def _validate_background(cls, value: str | None) -> str | None:
        """允许 HTTPS URL、内部媒体路径或用于清除背景的空字符串。

        Args:
            value: 背景图片地址、清除标记，或表示未提供的 None。

        Returns:
            去除首尾空白的有效地址或空字符串；未提供时返回 None。

        Raises:
            ValueError: 非空地址既不是 HTTPS URL，也不是内部媒体路径。
        """
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return ""
        if stripped.startswith("/plugin-media/"):
            return stripped
        lowered = stripped.lower()
        if lowered.startswith("https://"):
            return stripped
        raise ValueError(
            "background_image_url 必须使用 https 或为内部 /plugin-media/ 路径。"
        )


# 置顶插件 --------------------------------------------------------------


class PinnedPluginItem(BaseModel):
    """作者当前有效的单个置顶插件条目。"""

    plugin_id: str
    pinned_reason: str | None = Field(default=None, max_length=200)
    pinned_at: datetime
    plugin: Plugin | None = None


class PinCreate(BaseModel):
    """接口 ``POST /api/v1/me/pins`` 的请求体。"""

    plugin_id: str = Field(min_length=1)
    pinned_reason: str | None = Field(default=None, max_length=200)


class PinUpdate(BaseModel):
    """接口 ``PUT /api/v1/me/pins/{plugin_id}`` 的请求体。"""

    pinned_reason: str | None = Field(default=None, max_length=200)


# 插件元数据行内更新 -----------------------------------------------


class PluginMetadataPatch(BaseModel):
    """部分编辑插件元数据（显示名称、图标、分类与标签）。"""

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    # icon_url 接受 HTTPS URL 或上传接口生成的内部 /plugin-media/ 路径。
    # 具体协议和路径校验由 ``InlineEditService._validate_icon_url`` 执行，
    # 因此这里接受这两种形式。
    icon_url: str | None = None
    categories: list[str] | None = None
    tags: list[str] | None = None

    @field_validator("tags")
    @classmethod
    def _check_tags(cls, value: list[str] | None) -> list[str] | None:
        """限制标签总数和单个标签的长度。

        Args:
            value: 待校验的标签列表，未提供时为 None。

        Returns:
            校验通过的原始标签列表；未提供时返回 None。

        Raises:
            ValueError: 标签超过 10 个，或存在非字符串、长度不在 1 至 40 之间的标签。
        """
        if value is None:
            return None
        return _validate_tag_list(value)


# 收件箱 -----------------------------------------------------------------------


class InboxMessageSource(BaseModel):
    """触发收件箱消息的作者（提及、回复或治理操作）。"""

    author_id: str
    github_login: str
    display_name: str
    avatar_url: str | None = None


class InboxMessageLink(BaseModel):
    """收件箱消息的跳转信息。"""

    kind: InboxLinkKind
    plugin_id: str | None = None
    comment_id: int | None = None
    announcement_id: int | None = None


class InboxMessage(BaseModel):
    """返回给接收者的单条收件箱消息。"""

    id: int
    type: InboxMessageType
    status: InboxMessageStatus
    preview: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    source: InboxMessageSource | None = None
    link: InboxMessageLink | None = None
    related_plugin_id: str | None = None
    related_comment_id: int | None = None
    related_announcement_id: int | None = None
    created_at: datetime
    read_at: datetime | None = None


class InboxUnreadCount(BaseModel):
    """供导航栏通知铃使用的轻量未读数响应。"""

    count: int = Field(ge=0)


class InboxMessageListResponse(BaseModel):
    """分页收件箱消息响应。"""

    items: list[InboxMessage] = Field(default_factory=list)
    total: int = Field(ge=0)


# 公告 ---------------------------------------------------------------


class AnnouncementDTO(BaseModel):
    """供公开页面与管理端使用的公告数据。"""

    id: int
    title: str = Field(min_length=1, max_length=200)
    body_markdown: str = ""
    display_mode: DisplayModeLiteral
    severity: SeverityLiteral
    dismissible: bool = True
    enabled: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    audience: AudienceLiteral
    emit_inbox: bool = False
    dismiss_token: int = 0
    created_by: str
    created_at: datetime
    updated_at: datetime


class AnnouncementCreate(BaseModel):
    """接口 ``POST /api/v1/admin/announcements`` 的请求体。"""

    title: str = Field(min_length=1, max_length=200)
    body_markdown: str = ""
    display_mode: DisplayModeLiteral = "banner"
    severity: SeverityLiteral = "info"
    dismissible: bool = True
    enabled: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    audience: AudienceLiteral = "all"
    emit_inbox: bool = False


class AnnouncementUpdate(BaseModel):
    """接口 ``PUT /api/v1/admin/announcements/{id}`` 的请求体。"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    body_markdown: str | None = None
    display_mode: DisplayModeLiteral | None = None
    severity: SeverityLiteral | None = None
    dismissible: bool | None = None
    enabled: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    audience: AudienceLiteral | None = None
    emit_inbox: bool | None = None


class AnnouncementDismissResponse(BaseModel):
    """接口 ``POST /api/v1/announcements/{id}/dismiss`` 的结果。"""

    announcement_id: int
    dismissed: bool = True
    dismiss_token: int


class AnnouncementListResponse(BaseModel):
    """供管理界面使用的分页公告列表。"""

    items: list[AnnouncementDTO] = Field(default_factory=list)
    total: int = Field(ge=0)


# 精选条目 ------------------------------------------------------------


class CurationEntryDTO(BaseModel):
    """包含所引用插件或作者详细数据的精选条目。"""

    id: int
    slot_type: SlotTypeLiteral
    target_type: TargetTypeLiteral
    target_id: str
    signature_plugin_id: str | None = None
    sort_order: int = 0
    enabled: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    audience: AudienceLiteral = "all"
    display_meta: dict[str, Any] = Field(default_factory=dict)
    plugin: Plugin | None = None
    author: Author | None = None
    signature_plugin: Plugin | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class CurationEntryCreate(BaseModel):
    """接口 ``POST /api/v1/admin/curation/entries`` 的请求体。"""

    slot_type: SlotTypeLiteral
    target_type: TargetTypeLiteral
    target_id: str = Field(min_length=1)
    signature_plugin_id: str | None = None
    sort_order: int = 0
    enabled: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    audience: AudienceLiteral = "all"
    display_meta: dict[str, Any] = Field(default_factory=dict)


class CurationEntryUpdate(BaseModel):
    """接口 ``PUT /api/v1/admin/curation/entries/{id}`` 的请求体。"""

    slot_type: SlotTypeLiteral | None = None
    target_type: TargetTypeLiteral | None = None
    target_id: str | None = Field(default=None, min_length=1)
    signature_plugin_id: str | None = None
    sort_order: int | None = None
    enabled: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    audience: AudienceLiteral | None = None
    display_meta: dict[str, Any] | None = None


class CurationOrderUpdate(BaseModel):
    """接口 ``PUT /api/v1/admin/curation/order`` 的请求体。"""

    ids_in_order: list[int] = Field(min_length=1)

    @field_validator("ids_in_order")
    @classmethod
    def _unique_ids(cls, value: list[int]) -> list[int]:
        """拒绝排序请求数据中的重复 ID。

        Args:
            value: 按目标顺序排列的条目 ID 列表。

        Returns:
            不含重复 ID 的原始列表。

        Raises:
            ValueError: 列表包含重复 ID。
        """
        if len(set(value)) != len(value):
            raise ValueError("ids_in_order 不得包含重复项")
        return value


class CurationEntryListResponse(BaseModel):
    """供精选管理界面使用的列表数据。"""

    items: list[CurationEntryDTO] = Field(default_factory=list)
    total: int = Field(ge=0)


# 管理员批量操作 ----------------------------------------------------------


class BulkActionRequest(BaseModel):
    """接口 ``POST /api/v1/admin/plugins/bulk`` 的请求体。"""

    plugin_ids: list[str] = Field(min_length=1, max_length=100)
    action: BulkActionLiteral
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("plugin_ids")
    @classmethod
    def _non_empty_ids(cls, value: list[str]) -> list[str]:
        """拒绝批量请求中的空白插件 ID。

        Args:
            value: 待校验的插件 ID 列表。

        Returns:
            校验通过的原始插件 ID 列表。

        Raises:
            ValueError: 列表中存在非字符串或去除首尾空白后为空的插件 ID。
        """
        for plugin_id in value:
            if not isinstance(plugin_id, str) or not plugin_id.strip():
                raise ValueError("plugin_ids 中的各项必须为非空字符串")
        return value


class BulkActionItemError(BaseModel):
    """批量操作响应中单个条目的错误信息。"""

    code: str
    message: str


class BulkActionItemResult(BaseModel):
    """批量操作响应中单个插件的结果。"""

    plugin_id: str
    ok: bool
    after: Plugin | None = None
    error: BulkActionItemError | None = None


class BulkActionResult(BaseModel):
    """接口 ``POST /api/v1/admin/plugins/bulk`` 的响应体（HTTP 207）。"""

    results: list[BulkActionItemResult] = Field(default_factory=list)


# 市场首页聚合数据 -------------------------------------------------------


class CategoryPreviewSection(BaseModel):
    """包含实际总数的单个分类预览数据。"""

    items: list[Plugin] = Field(default_factory=list)
    total: int = 0


class MarketHome(BaseModel):
    """接口 ``GET /api/v1/market/home`` 的聚合响应。"""

    showcase: list[CurationEntryDTO] = Field(default_factory=list)
    featured_plugins: list[Plugin] = Field(default_factory=list)
    trending_authors: list[TrendingItem] = Field(default_factory=list)
    latest: list[Plugin] = Field(default_factory=list)
    top_rated: list[Plugin] = Field(default_factory=list)
    categories_preview: dict[str, CategoryPreviewSection] = Field(default_factory=dict)
    stats: MarketStats
    active_announcements: list[AnnouncementDTO] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 技能市场数据模型
# ---------------------------------------------------------------------------


class Skill(BaseModel):
    """市场技能记录（列表项或详情）。"""

    skill_id: str
    display_name: str
    description: str
    readme_markdown: str | None = None
    owner_id: str
    owner_login: str | None = None
    owner_display_name: str | None = None
    owner_avatar_url: str | None = None
    icon_url: str | None = None
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: str  # SkillStatus
    trust_level: str  # TrustLevel
    latest_version: str | None = None
    download_count: int = 0
    likes_count: int = 0
    comments_count: int = 0
    rating_avg: float = 0.0
    rating_count: int = 0
    viewer_has_liked: bool = False
    viewer_rating: int | None = None
    created_at: datetime
    updated_at: datetime


class SkillVersion(BaseModel):
    """可安装的技能版本记录。"""

    version: str
    package_size: int
    checksum_sha256: str
    release_notes: str | None = None
    min_mofox_version: str | None = None
    download_count: int = 0
    created_at: datetime


class SkillCreate(BaseModel):
    """发布新技能的请求体，ZIP 包通过路由中的 UploadFile 上传。"""

    skill_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    release_notes: str | None = None
    min_mofox_version: str | None = None
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class SkillVersionCreate(BaseModel):
    """发布技能新版本的请求体，ZIP 包通过路由中的 UploadFile 上传。"""

    version: str = Field(min_length=1)
    release_notes: str | None = None
    min_mofox_version: str | None = None


class SkillUpdate(BaseModel):
    """更新技能可变元数据的请求体。"""

    display_name: str | None = Field(default=None, min_length=1)
    icon_url: str | None = None
    categories: list[str] | None = None
    tags: list[str] | None = None


class SkillComment(BaseModel):
    """用户对技能的评论。"""

    id: int
    skill_id: str
    parent_id: int | None
    content: str
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False
    author: CommentAuthor
    mentions: list[MentionCandidate] = Field(default_factory=list)


class SkillCommentCreate(BaseModel):
    """提交技能评论的请求体。"""

    content: str = Field(min_length=1, max_length=4000)
    parent_id: int | None = None


class SkillCommentListResponse(BaseModel):
    """分页技能评论响应。"""

    items: list[SkillComment]
    total: int


class SkillListResponse(BaseModel):
    """分页技能列表响应。"""

    items: list[Skill]
    total: int


class SkillRatingInfo(BaseModel):
    """技能的评分汇总统计。"""

    skill_id: str
    rating_avg: float
    rating_count: int
    distribution: dict[str, int] = Field(default_factory=dict)
    viewer_rating: int | None = None


class SkillInstallRecord(BaseModel):
    """记录技能安装或下载后的响应。"""

    skill_id: str
    version: str
    download_count: int


class SkillVersionListResponse(BaseModel):
    """技能版本列表响应。"""

    items: list[SkillVersion]
    total: int
