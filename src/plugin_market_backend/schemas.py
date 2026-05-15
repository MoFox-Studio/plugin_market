"""Pydantic schemas for the plugin market API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator

from plugin_market_backend.enums import AuthorType, PluginStatus, ReviewAction, SyncStatus, TrustLevel, VersionStatus


def _validate_sha256(value: str) -> str:
    """Validate a sha256 hex string."""

    if len(value) != 64 or any(char not in "0123456789abcdefABCDEF" for char in value):
        raise ValueError("checksum_sha256 must be a 64-character hexadecimal string")
    return value.lower()


class Author(BaseModel):
    """Author identity response."""

    author_id: str
    github_user_id: str | None = None
    github_login: str
    display_name: str
    avatar_url: str | None = None
    author_type: AuthorType
    verified_at: datetime | None = None
    is_admin: bool = False


class AuthStatus(BaseModel):
    """Current browser/API authentication state."""

    authenticated: bool
    user: Author | None = None


class PluginCreate(BaseModel):
    """Request body for registering a plugin."""

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
    """Request body for updating mutable plugin metadata."""

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
    """Resolved plugin dependency for detail views."""

    plugin_id: str
    raw: str
    version_spec: str | None = None
    exists_in_market: bool = False
    display_name: str | None = None
    icon_url: str | None = None


class Plugin(BaseModel):
    """Market plugin record."""

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
    """Request body for submitting a plugin version."""

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

    @field_validator("checksum_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        """Require 64-character hex sha256 values."""

        return _validate_sha256(value)


class PluginVersion(BaseModel):
    """Market plugin version record."""

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
    """Request body for updating a version from CLI sync."""

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
        """Validate optional sha256 values."""

        return _validate_sha256(value) if value is not None else None


class VersionStatusItem(BaseModel):
    """Condensed version status returned to CLI."""

    version: str
    status: VersionStatus
    is_yanked: bool
    last_sync_status: SyncStatus
    last_sync_error: str | None


class PluginStatusResponse(BaseModel):
    """Plugin status response returned to CLI."""

    plugin_id: str
    plugin_status: PluginStatus
    versions: list[VersionStatusItem]


class InstallInfo(BaseModel):
    """Install metadata returned to clients and CLI."""

    plugin: Plugin
    version: PluginVersion


class MarketStats(BaseModel):
    """Admin stats response."""

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
    """Audit record for review and sync operations."""

    target_type: str
    target_id: str
    action: ReviewAction
    status_before: str | None = None
    status_after: str | None = None
    reason: str | None = None
    operator_id: str
    created_at: datetime


class ReviewDecision(BaseModel):
    """Admin review request body."""

    reason: str | None = None


class PluginListResponse(BaseModel):
    """Paginated plugin list response."""

    items: list[Plugin]
    total: int


class VersionListResponse(BaseModel):
    """Plugin version list response."""

    items: list[PluginVersion]
    total: int


class TaxonomyResponse(BaseModel):
    """Categories or tags response."""

    items: list[str]


class WebhookResponse(BaseModel):
    """GitHub webhook intake response."""

    accepted: bool
    event_id: str


class PluginReadmeResponse(BaseModel):
    """Rendered README payload for plugin detail pages."""

    plugin_id: str
    exists: bool
    html: str | None = None


class PluginDependenciesResponse(BaseModel):
    """Resolved plugin dependency payload for detail pages."""

    plugin_id: str
    items: list[PluginDependency] = Field(default_factory=list)


class CommentAuthor(BaseModel):
    """Compact author block returned with comments."""

    author_id: str
    github_login: str
    display_name: str
    avatar_url: str | None = None
    is_admin: bool = False


class Comment(BaseModel):
    """User comment on a plugin."""

    id: int
    plugin_id: str
    parent_id: int | None
    content: str
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False
    author: CommentAuthor


class CommentCreate(BaseModel):
    """Request body for submitting a comment."""

    content: str = Field(min_length=1, max_length=4000)
    parent_id: int | None = None


class CommentListResponse(BaseModel):
    """Paginated comment response."""

    items: list[Comment]
    total: int


class RatingRequest(BaseModel):
    """Request body for rating a plugin."""

    score: int = Field(ge=1, le=5)


class RatingSummary(BaseModel):
    """Aggregated rating stats for a plugin."""

    plugin_id: str
    rating_avg: float
    rating_count: int
    distribution: dict[str, int] = Field(default_factory=dict)
    viewer_rating: int | None = None


class LikeResponse(BaseModel):
    """Like toggle result."""

    plugin_id: str
    liked: bool
    likes_count: int


class ActivityPoint(BaseModel):
    """Daily market activity bucket for the admin dashboard."""

    date: str
    plugins_created: int = 0
    versions_created: int = 0
    comments_created: int = 0
    ratings_created: int = 0
    review_events: int = 0


class PluginGovernanceSnapshot(BaseModel):
    """Detailed plugin governance data for admin and owner views."""

    plugin: Plugin
    versions: list[PluginVersion] = Field(default_factory=list)
    recent_reviews: list[ReviewRecord] = Field(default_factory=list)


class AdminDashboard(BaseModel):
    """Aggregated admin dashboard payload."""

    stats: MarketStats
    plugin_status_breakdown: dict[str, int] = Field(default_factory=dict)
    version_status_breakdown: dict[str, int] = Field(default_factory=dict)
    activity: list[ActivityPoint] = Field(default_factory=list)
    popular_plugins: list[Plugin] = Field(default_factory=list)


class CommunitySnapshot(BaseModel):
    """Aggregated community data for the detail view."""

    plugin: Plugin
    rating: RatingSummary
    recent_comments: list[Comment] = Field(default_factory=list)


class TrendingItem(BaseModel):
    """Lightweight trending author or stat entry."""

    author_id: str
    github_login: str
    display_name: str
    avatar_url: str | None = None
    plugins_count: int
    likes_received: int
    downloads_total: int
