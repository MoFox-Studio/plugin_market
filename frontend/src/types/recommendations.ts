import type { Plugin } from './index';
export interface Interests {
  categories: string[];
  tags: string[];
}
export interface RecommendationPreferences {
  personalization_enabled: boolean;
  interests: Interests;
  ignored_plugins: {
    plugin_id: string;
    reason: 'not_interested' | 'already_have';
    expires_at: string;
  }[];
  reduced_categories: { category: string; expires_at: string }[];
  revision: number;
  updated_at: string | null;
  feedback_retention_days: number;
}
export interface RecommendationFeedback {
  type:
    | 'not_interested'
    | 'already_have'
    | 'restore_plugin'
    | 'reduce_category'
    | 'restore_category';
  plugin_id?: string;
  category?: string;
}
export interface RecommendationItem {
  plugin: Plugin;
  recommended_version: string;
  compatibility: 'compatible' | 'unknown';
  reasons: { code: string; label: string }[];
}
export interface RecommendationResponse {
  recommendation_id: string;
  algorithm_version: string;
  mode: 'personalized' | 'contextual' | 'popular';
  generated_at: string;
  items: RecommendationItem[];
  next_cursor: string | null;
}
export interface RecommendationContext {
  placement: 'home' | 'detail';
  context_plugin_id?: string;
}
