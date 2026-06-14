"""Pydantic schemas for the plugin market API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

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


class AuthorFollowState(BaseModel):
    """Follow toggle state for an author."""

    author_id: str
    following: bool
    followers_count: int


class PluginSubscriptionState(BaseModel):
    """Subscription toggle state for a plugin."""

    plugin_id: str
    subscribed: bool
    subscriptions_count: int


class AccessTokenStatus(BaseModel):
    """Metadata describing the single active access token for an author."""

    author_id: str
    has_token: bool
    token_preview: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_used_at: datetime | None = None


class AccessTokenRotateResponse(BaseModel):
    """Plaintext token returned only at creation / rotation time."""

    author_id: str
    token: str
    token_preview: str
    created_at: datetime
    updated_at: datetime


class MachineSubscriptionItem(BaseModel):
    """One subscribed plugin returned to machine clients."""

    plugin_id: str
    display_name: str | None = None
    latest_version: str | None = None
    updated_at: datetime | None = None


class MachineSubscriptionListResponse(BaseModel):
    """Subscribed plugin list returned to machine clients."""

    author_id: str
    items: list[MachineSubscriptionItem] = Field(default_factory=list)
    total: int = Field(ge=0)


class MySubscriptionItem(BaseModel):
    """One subscribed plugin in the viewer's subscription list."""

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
    """Viewer's subscribed plugin list."""

    author_id: str
    items: list[MySubscriptionItem] = Field(default_factory=list)
    total: int = Field(ge=0)


class MyFollowItem(BaseModel):
    """One followed author in the viewer's follow list."""

    author_id: str
    github_login: str
    display_name: str
    avatar_url: str | None = None
    author_type: AuthorType
    followed_at: datetime


class MyFollowListResponse(BaseModel):
    """Viewer's followed author list."""

    author_id: str
    items: list[MyFollowItem] = Field(default_factory=list)
    total: int = Field(ge=0)


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
    readme_markdown: str | None = None

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


class MentionCandidate(BaseModel):
    """Resolved mention candidate for search and comment rendering."""

    author_id: str
    github_login: str
    display_name: str
    avatar_url: str | None = None


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
    mentions: list[MentionCandidate] = Field(default_factory=list)


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
    bio: str | None = None
    plugins_count: int
    likes_received: int
    downloads_total: int
    rating_avg: float = 0.0
    rating_count: int = 0
    best_plugin: "TrendingPlugin | None" = None


class TrendingPlugin(BaseModel):
    """Compact plugin block used as fallback signature for an author."""

    plugin_id: str
    display_name: str
    summary: str
    icon_url: str | None = None
    latest_version: str | None = None


# ---------------------------------------------------------------------------
# plugin-market-overhaul phase 1 (task 2): incremental Pydantic schemas
# ---------------------------------------------------------------------------


# Shared literal vocabularies -------------------------------------------------

AudienceLiteral = Literal[
    "all",
    "logged_in",
    "anonymous",
    "admins",
    "authors_with_plugin",
]
"""Audience selectors shared by curation entries and announcements."""

DisplayModeLiteral = Literal["banner", "modal"]
"""Announcement presentation modes."""

SeverityLiteral = Literal["info", "warning", "critical"]
"""Announcement severity levels."""

SlotTypeLiteral = Literal[
    "featured_plugin",
    "featured_author",
    "signature_plugin",
    "hero",
    "sidebar",
]
"""Curation slot kinds rendered in the home showcase."""

TargetTypeLiteral = Literal["plugin", "author"]
"""Resource a curation entry references."""

InboxMessageType = Literal[
    "mention",
    "reply",
    "governance",
    "announcement",
    "author_activity",
    "plugin_activity",
    "system",
]
"""Inbox message categories."""

InboxMessageStatus = Literal["unread", "read", "revoked"]
"""Inbox message lifecycle status."""

InboxLinkKind = Literal["comment", "plugin", "announcement", "system"]
"""Where activating an inbox message should navigate."""

BulkActionLiteral = Literal[
    "publish",
    "reject",
    "block",
    "deprecate",
    "set_trust_level",
    "delete",
]
"""Bulk admin actions accepted by ``POST /api/v1/admin/plugins/bulk``."""


# Field-level helpers ---------------------------------------------------------


def _ensure_https(value: HttpUrl | None) -> HttpUrl | None:
    """Reject non-https URLs for sensitive media references."""

    if value is None:
        return None
    if value.scheme != "https":
        raise ValueError("URL must use https scheme")
    return value


def _validate_tag_list(values: list[str]) -> list[str]:
    """Apply tag-set length and per-tag length constraints."""

    if len(values) > 10:
        raise ValueError("at most 10 tags are allowed")
    for tag in values:
        if not isinstance(tag, str) or not (1 <= len(tag) <= 40):
            raise ValueError("each tag must be between 1 and 40 characters")
    return values


# Author profile / personal space --------------------------------------------


class AuthorProfile(BaseModel):
    """Personal-space profile payload returned to the Market frontend."""

    author_id: str
    bio: str = Field(default="", max_length=2000)
    background_image_url: str | None = None
    background_image_kind: Literal["url", "upload"] = "url"
    updated_at: datetime | None = None


class AuthorProfileUpdate(BaseModel):
    """Partial update payload for ``PUT /api/v1/me/profile``."""

    bio: str | None = Field(default=None, max_length=2000)
    # Accept https URLs OR an internal /plugin-media/ path (uploaded image),
    # OR an empty string meaning "clear the current background".
    background_image_url: str | None = None

    @field_validator("background_image_url")
    @classmethod
    def _validate_background(cls, value: str | None) -> str | None:
        """Allow https URL, internal media path, or empty string (clear)."""

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
            "background_image_url must use https or be an internal /plugin-media/ path."
        )


# Pinned plugins --------------------------------------------------------------


class PinnedPluginItem(BaseModel):
    """One active pinned-plugin slot for an author."""

    plugin_id: str
    pinned_reason: str | None = Field(default=None, max_length=200)
    pinned_at: datetime
    plugin: Plugin | None = None


class PinCreate(BaseModel):
    """Request body for ``POST /api/v1/me/pins``."""

    plugin_id: str = Field(min_length=1)
    pinned_reason: str | None = Field(default=None, max_length=200)


class PinUpdate(BaseModel):
    """Request body for ``PUT /api/v1/me/pins/{plugin_id}``."""

    pinned_reason: str | None = Field(default=None, max_length=200)


# Inline plugin metadata patch -----------------------------------------------


class PluginMetadataPatch(BaseModel):
    """Partial plugin metadata edit (display_name / icon / categories / tags)."""

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    # icon_url accepts an https URL OR an internal /plugin-media/ path produced
    # by the upload endpoint. Detailed scheme/path validation lives in
    # ``InlineEditService._validate_icon_url`` so both shapes are accepted.
    icon_url: str | None = None
    categories: list[str] | None = None
    tags: list[str] | None = None

    @field_validator("tags")
    @classmethod
    def _check_tags(cls, value: list[str] | None) -> list[str] | None:
        """Cap tag count and bound individual tag lengths."""

        if value is None:
            return None
        return _validate_tag_list(value)


# Inbox -----------------------------------------------------------------------


class InboxMessageSource(BaseModel):
    """Author who triggered an inbox message (mention / reply / governance)."""

    author_id: str
    github_login: str
    display_name: str
    avatar_url: str | None = None


class InboxMessageLink(BaseModel):
    """Navigation hint for an inbox message."""

    kind: InboxLinkKind
    plugin_id: str | None = None
    comment_id: int | None = None
    announcement_id: int | None = None


class InboxMessage(BaseModel):
    """Single inbox message returned to the recipient."""

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
    """Lightweight unread-count response used by the navbar bell."""

    count: int = Field(ge=0)


class InboxMessageListResponse(BaseModel):
    """Paginated inbox message response."""

    items: list[InboxMessage] = Field(default_factory=list)
    total: int = Field(ge=0)


# Announcements ---------------------------------------------------------------


class AnnouncementDTO(BaseModel):
    """Announcement projected for both public and admin consumption."""

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
    """Request body for ``POST /api/v1/admin/announcements``."""

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
    """Request body for ``PUT /api/v1/admin/announcements/{id}``."""

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
    """Result of ``POST /api/v1/announcements/{id}/dismiss``."""

    announcement_id: int
    dismissed: bool = True
    dismiss_token: int


class AnnouncementListResponse(BaseModel):
    """Paginated announcement list for admin surfaces."""

    items: list[AnnouncementDTO] = Field(default_factory=list)
    total: int = Field(ge=0)


# Curation entries ------------------------------------------------------------


class CurationEntryDTO(BaseModel):
    """Curation entry expanded with referenced plugin / author payloads."""

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
    """Request body for ``POST /api/v1/admin/curation/entries``."""

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
    """Request body for ``PUT /api/v1/admin/curation/entries/{id}``."""

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
    """Request body for ``PUT /api/v1/admin/curation/order``."""

    ids_in_order: list[int] = Field(min_length=1)

    @field_validator("ids_in_order")
    @classmethod
    def _unique_ids(cls, value: list[int]) -> list[int]:
        """Reject duplicate ids in the ordering payload."""

        if len(set(value)) != len(value):
            raise ValueError("ids_in_order must not contain duplicates")
        return value


class CurationEntryListResponse(BaseModel):
    """List payload for admin curation screens."""

    items: list[CurationEntryDTO] = Field(default_factory=list)
    total: int = Field(ge=0)


# Admin bulk actions ----------------------------------------------------------


class BulkActionRequest(BaseModel):
    """Request body for ``POST /api/v1/admin/plugins/bulk``."""

    plugin_ids: list[str] = Field(min_length=1, max_length=100)
    action: BulkActionLiteral
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("plugin_ids")
    @classmethod
    def _non_empty_ids(cls, value: list[str]) -> list[str]:
        """Reject blank plugin ids inside the batch."""

        for plugin_id in value:
            if not isinstance(plugin_id, str) or not plugin_id.strip():
                raise ValueError("plugin_ids entries must be non-empty strings")
        return value


class BulkActionItemError(BaseModel):
    """Per-row error payload inside a bulk-action response."""

    code: str
    message: str


class BulkActionItemResult(BaseModel):
    """Result for a single plugin inside a bulk-action response."""

    plugin_id: str
    ok: bool
    after: Plugin | None = None
    error: BulkActionItemError | None = None


class BulkActionResult(BaseModel):
    """Response body for ``POST /api/v1/admin/plugins/bulk`` (HTTP 207)."""

    results: list[BulkActionItemResult] = Field(default_factory=list)


# Market home aggregate -------------------------------------------------------


class MarketHome(BaseModel):
    """Aggregate response for ``GET /api/v1/market/home``."""

    showcase: list[CurationEntryDTO] = Field(default_factory=list)
    featured_plugins: list[Plugin] = Field(default_factory=list)
    trending_authors: list[TrendingItem] = Field(default_factory=list)
    latest: list[Plugin] = Field(default_factory=list)
    top_rated: list[Plugin] = Field(default_factory=list)
    categories_preview: dict[str, list[Plugin]] = Field(default_factory=dict)
    stats: MarketStats
    active_announcements: list[AnnouncementDTO] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Skill market schemas
# ---------------------------------------------------------------------------


class Skill(BaseModel):
    """Market skill record (list item / detail)."""

    skill_id: str
    display_name: str
    description: str
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
    """Installable skill version record."""

    version: str
    package_size: int
    checksum_sha256: str
    release_notes: str | None = None
    min_mofox_version: str | None = None
    download_count: int = 0
    created_at: datetime


class SkillCreate(BaseModel):
    """Request body for publishing a new skill (zip via UploadFile in route)."""

    skill_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_\-]*$")
    version: str = Field(min_length=1)
    release_notes: str | None = None
    min_mofox_version: str | None = None
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class SkillVersionCreate(BaseModel):
    """Request body for publishing a new skill version (zip via UploadFile in route)."""

    version: str = Field(min_length=1)
    release_notes: str | None = None
    min_mofox_version: str | None = None


class SkillUpdate(BaseModel):
    """Request body for updating mutable skill metadata."""

    display_name: str | None = Field(default=None, min_length=1)
    icon_url: str | None = None
    categories: list[str] | None = None
    tags: list[str] | None = None


class SkillComment(BaseModel):
    """User comment on a skill."""

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
    """Request body for submitting a comment on a skill."""

    content: str = Field(min_length=1, max_length=4000)
    parent_id: int | None = None


class SkillCommentListResponse(BaseModel):
    """Paginated skill comment response."""

    items: list[SkillComment]
    total: int


class SkillListResponse(BaseModel):
    """Paginated skill list response."""

    items: list[Skill]
    total: int


class SkillRatingInfo(BaseModel):
    """Aggregated rating stats for a skill."""

    skill_id: str
    rating_avg: float
    rating_count: int
    distribution: dict[str, int] = Field(default_factory=dict)
    viewer_rating: int | None = None


class SkillInstallRecord(BaseModel):
    """Response after recording a skill install / download."""

    skill_id: str
    version: str
    download_count: int


class SkillVersionListResponse(BaseModel):
    """Skill version list response."""

    items: list[SkillVersion]
    total: int
