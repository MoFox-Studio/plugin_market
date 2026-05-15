/**
 * Shared type definitions for the plugin market frontend
 */

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
  action: string
  target_id: string
  status_before?: string
  status_after?: string
  operator_id: string
  created_at: string
}

export interface Comment {
  id: string
  content: string
  created_at: string
  author: CommentAuthor
}

export interface CommentAuthor {
  author_id: string
  github_login: string
  display_name: string
  avatar_url?: string
  is_admin?: boolean
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
}

export interface FeaturedData {
  ranking?: Plugin[]
  top_rated?: Plugin[]
  latest?: Plugin[]
  [key: string]: Plugin[] | undefined
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
