/**
 * Shared type definitions for the plugin market frontend
 */

export type Audience = 'all' | 'logged_in' | 'anonymous' | 'admins' | 'authors_with_plugin'
export type DisplayMode = 'banner' | 'modal'
export type Severity = 'info' | 'warning' | 'critical'
export type SlotType = 'featured_plugin' | 'featured_author' | 'signature_plugin' | 'hero' | 'sidebar'
export type TargetType = 'plugin' | 'author'
export type InboxMessageType = 'mention' | 'reply' | 'governance' | 'announcement' | 'author_activity' | 'plugin_activity' | 'system'
export type InboxMessageStatus = 'unread' | 'read' | 'revoked'
export type InboxLinkKind = 'comment' | 'plugin' | 'announcement' | 'system'
export type BulkAction = 'publish' | 'reject' | 'block' | 'deprecate' | 'set_trust_level' | 'delete'

export interface Author {
  author_id: string
  github_user_id?: string | null
  github_login: string
  display_name: string
  avatar_url?: string | null
  author_type?: string
  verified_at?: string | null
  is_admin: boolean
}

export interface AuthStatus {
  authenticated: boolean
  user?: Author | null
}

export interface AuthorProfile {
  author_id: string
  bio: string
  background_image_url?: string | null
  background_image_kind: 'url' | 'upload'
  updated_at?: string | null
}

export interface AuthorProfileUpdate {
  bio?: string | null
  background_image_url?: string | null
}

export interface AuthorFollowState {
  author_id: string
  following: boolean
  followers_count: number
}

export interface AccessTokenStatus {
  author_id: string
  has_token: boolean
  token_preview?: string | null
  created_at?: string | null
  updated_at?: string | null
  last_used_at?: string | null
}

export interface AccessTokenRotateResponse {
  author_id: string
  token: string
  token_preview: string
  created_at: string
  updated_at: string
}

export interface Plugin {
  plugin_id: string
  display_name: string
  summary: string
  description?: string
  icon_url?: string
  status: string
  trust_level: string
  latest_version?: string
  latest_version_published_at?: string
  owner_id: string
  owner_login?: string
  owner_display_name?: string
  owner_avatar_url?: string
  repository_url: string
  homepage?: string
  license?: string
  categories?: string[]
  tags?: string[]
  maintainers: string[]
  likes_count: number
  downloads_count: number
  comments_count: number
  rating_avg: number
  rating_count: number
  viewer_has_liked?: boolean
  updated_at: string
  created_at?: string
}

export interface PluginSubscriptionState {
  plugin_id: string
  subscribed: boolean
  subscriptions_count: number
}

export interface MySubscriptionItem {
  plugin_id: string
  display_name: string
  summary: string
  icon_url?: string | null
  status: string
  owner_id: string
  owner_login?: string | null
  owner_display_name?: string | null
  latest_version?: string | null
  updated_at?: string | null
  subscribed_at: string
}

export interface MySubscriptionListResponse {
  author_id: string
  items: MySubscriptionItem[]
  total: number
}

export interface MyFollowItem {
  author_id: string
  github_login: string
  display_name: string
  avatar_url?: string | null
  author_type: string
  followed_at: string
}

export interface MyFollowListResponse {
  author_id: string
  items: MyFollowItem[]
  total: number
}

export interface PluginVersion {
  version: string
  status: string
  release_title?: string
  published_at?: string
  file_size: number
  download_count: number
  plugin_api_version: string
  min_host_version: string
  max_host_version?: string
  supported_platforms?: string[]
  is_prerelease?: boolean
  is_yanked?: boolean
  release_url: string
  asset_download_url: string
}

export interface PluginSnapshot {
  plugin: Plugin
  versions: PluginVersion[]
  recent_reviews?: ReviewItem[]
  rating?: RatingInfo
}

export interface RatingInfo {
  distribution?: Record<string, number>
  viewer_rating?: number
}

export interface ReviewItem {
  id?: string
  target_type: string
  action: string
  target_id: string
  status_before?: string
  status_after?: string
  reason?: string | null
  operator_id: string
  created_at: string
}

export interface Comment {
  id: string
  plugin_id?: string
  parent_id?: number | null
  content: string
  created_at: string
  updated_at?: string
  is_deleted?: boolean
  author: CommentAuthor
  mentions?: MentionCandidate[]
}

export interface CommentAuthor {
  author_id: string
  github_login: string
  display_name: string
  avatar_url?: string
  is_admin?: boolean
}

export interface MentionCandidate {
  author_id: string
  github_login: string
  display_name: string
  avatar_url?: string | null
}

export interface Dependency {
  plugin_id: string
  display_name?: string
  icon_url?: string
  version_spec?: string
  exists_in_market?: boolean
}

export interface MarketStats {
  published_plugins?: number
  plugins_total?: number
  versions_total?: number
  authors_total?: number
  comments_total?: number
  ratings_total?: number
  likes_total?: number
  downloads_total?: number
  pending_plugins?: number
  pending_versions?: number
  webhooks_total?: number
}

export interface TrendingItem {
  author_id: string
  github_login: string
  display_name: string
  avatar_url?: string | null
  bio?: string | null
  plugins_count: number
  likes_received: number
  downloads_total: number
  rating_avg?: number
  rating_count?: number
  best_plugin?: TrendingPlugin | null
}

export interface TrendingPlugin {
  plugin_id: string
  display_name: string
  summary: string
  icon_url?: string | null
  latest_version?: string | null
}

export interface FeaturedData {
  ranking?: Plugin[]
  top_rated?: Plugin[]
  latest?: Plugin[]
  [key: string]: Plugin[] | undefined
}

export interface PinnedPlugin {
  plugin_id: string
  pinned_reason?: string | null
  pinned_at: string
  plugin?: Plugin | null
}

export interface PinCreate {
  plugin_id: string
  pinned_reason?: string | null
}

export interface PinUpdate {
  pinned_reason?: string | null
}

export interface PluginMetadataPatch {
  display_name?: string | null
  icon_url?: string | null
  categories?: string[] | null
  tags?: string[] | null
}

export interface InboxMessageSource {
  author_id: string
  github_login: string
  display_name: string
  avatar_url?: string | null
}

export interface InboxMessageLink {
  kind: InboxLinkKind
  plugin_id?: string | null
  comment_id?: number | null
  announcement_id?: number | null
}

export interface InboxMessage {
  id: number
  type: InboxMessageType
  status: InboxMessageStatus
  preview: string
  payload: Record<string, unknown>
  source?: InboxMessageSource | null
  link?: InboxMessageLink | null
  related_plugin_id?: string | null
  related_comment_id?: number | null
  related_announcement_id?: number | null
  created_at: string
  read_at?: string | null
}

export interface InboxUnreadCount {
  count: number
}

export interface InboxMessageListResponse {
  items: InboxMessage[]
  total: number
}

export interface Announcement {
  id: number
  title: string
  body_markdown: string
  display_mode: DisplayMode
  severity: Severity
  dismissible: boolean
  enabled: boolean
  starts_at?: string | null
  ends_at?: string | null
  audience: Audience
  emit_inbox: boolean
  dismiss_token: number
  created_by: string
  created_at: string
  updated_at: string
}

export interface AnnouncementCreate {
  title: string
  body_markdown?: string
  display_mode?: DisplayMode
  severity?: Severity
  dismissible?: boolean
  enabled?: boolean
  starts_at?: string | null
  ends_at?: string | null
  audience?: Audience
  emit_inbox?: boolean
}

export interface AnnouncementUpdate {
  title?: string | null
  body_markdown?: string | null
  display_mode?: DisplayMode | null
  severity?: Severity | null
  dismissible?: boolean | null
  enabled?: boolean | null
  starts_at?: string | null
  ends_at?: string | null
  audience?: Audience | null
  emit_inbox?: boolean | null
}

export interface AnnouncementDismissResponse {
  announcement_id: number
  dismissed: boolean
  dismiss_token: number
}

export interface AnnouncementListResponse {
  items: Announcement[]
  total: number
}

export interface CurationEntry {
  id: number
  slot_type: SlotType
  target_type: TargetType
  target_id: string
  signature_plugin_id?: string | null
  sort_order: number
  enabled: boolean
  starts_at?: string | null
  ends_at?: string | null
  audience: Audience
  display_meta: Record<string, unknown>
  plugin?: Plugin | null
  author?: Author | null
  signature_plugin?: Plugin | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface CurationEntryCreate {
  slot_type: SlotType
  target_type: TargetType
  target_id: string
  signature_plugin_id?: string | null
  sort_order?: number
  enabled?: boolean
  starts_at?: string | null
  ends_at?: string | null
  audience?: Audience
  display_meta?: Record<string, unknown>
}

export interface CurationEntryUpdate {
  slot_type?: SlotType | null
  target_type?: TargetType | null
  target_id?: string | null
  signature_plugin_id?: string | null
  sort_order?: number | null
  enabled?: boolean | null
  starts_at?: string | null
  ends_at?: string | null
  audience?: Audience | null
  display_meta?: Record<string, unknown> | null
}

export interface CurationEntryListResponse {
  items: CurationEntry[]
  total: number
}

export interface CurationOrderUpdate {
  ids_in_order: number[]
}

export interface BulkActionRequest {
  plugin_ids: string[]
  action: BulkAction
  params?: Record<string, unknown>
}

export interface BulkActionItemError {
  code: string
  message: string
}

export interface BulkActionItemResult {
  plugin_id: string
  ok: boolean
  after?: Plugin | null
  error?: BulkActionItemError | null
}

export interface BulkActionResult {
  results: BulkActionItemResult[]
}

export interface CategoryPreviewSection {
  items: Plugin[]
  total: number
}

export interface MarketHome {
  showcase: CurationEntry[]
  featured_plugins: Plugin[]
  trending_authors: TrendingItem[]
  latest: Plugin[]
  top_rated: Plugin[]
  categories_preview: Record<string, CategoryPreviewSection>
  stats: MarketStats
  active_announcements: Announcement[]
}

export interface SystemInfo {
  status: string
  environment: string
  database: string
  database_path?: string
  uptime_seconds: number
  started_at: string
  review_required: boolean
  github_oauth_configured: boolean
  github_webhook_configured: boolean
  stats: {
    latest_review_at?: string
  }
}

export interface DashboardData {
  stats: {
    plugins_total: number
    versions_total: number
    comments_total: number
    ratings_total: number
    likes_total: number
    downloads_total: number
    authors_total: number
    webhooks_total: number
    pending_plugins: number
    pending_versions: number
  }
  activity?: ActivityDay[]
  plugin_status_breakdown?: Record<string, number>
  version_status_breakdown?: Record<string, number>
  popular_plugins?: Plugin[]
}

export interface ActivityDay {
  date: string
  plugins_created: number
  comments_created: number
  ratings_created: number
}

// ── Skill market types ──

export interface Skill {
  skill_id: string
  display_name: string
  description: string
  readme_markdown?: string | null
  owner_id: string
  owner_login?: string | null
  owner_display_name?: string | null
  owner_avatar_url?: string | null
  icon_url?: string | null
  categories: string[]
  tags: string[]
  status: string
  trust_level: string
  latest_version?: string | null
  download_count: number
  likes_count: number
  comments_count: number
  rating_avg: number
  rating_count: number
  viewer_has_liked?: boolean
  created_at: string
  updated_at: string
}

export interface SkillVersion {
  version: string
  package_size: number
  checksum_sha256: string
  release_notes?: string | null
  min_mofox_version?: string | null
  download_count: number
  created_at: string
}

export interface SkillComment {
  id: number
  skill_id: string
  parent_id?: number | null
  content: string
  created_at: string
  updated_at?: string
  is_deleted?: boolean
  author: CommentAuthor
}

export interface SkillCommentCreate {
  content: string
  parent_id?: number | null
}

export interface SkillListResponse {
  items: Skill[]
  total: number
}

export interface SkillCommentListResponse {
  items: SkillComment[]
  total: number
}

export interface SkillRatingInfo {
  distribution?: Record<string, number>
  viewer_rating?: number
}

export interface SkillInstallRecord {
  skill_id: string
  download_count: number
}

export interface SkillVersionListResponse {
  items: SkillVersion[]
  total: number
}

export interface SkillCreate {
  skill_id: string
  version: string
  release_notes?: string | null
  min_mofox_version?: string | null
  categories?: string[]
  tags?: string[]
}

export interface SkillVersionCreate {
  version: string
  release_notes?: string | null
  min_mofox_version?: string | null
}

export interface SkillUpdate {
  display_name?: string | null
  icon_url?: string | null
  categories?: string[] | null
  tags?: string[] | null
}
