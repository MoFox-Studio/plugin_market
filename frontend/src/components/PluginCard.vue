<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import {
  categoryLabel,
  formatNumber,
  formatRelative,
  trustLevelLabel,
} from '@/utils/format';
import { useSubscriptionStore } from '@/stores/subscriptions';
import AppIcon from '@/components/AppIcon.vue';
import CatalogListing from '@/components/catalog/CatalogListing.vue';
import type { Plugin } from '@/types';
const props = defineProps<{ plugin: Plugin; featured?: boolean; number?: number; lead?: boolean; compact?: boolean }>();
const subscriptions = useSubscriptionStore();
const brokenIcon = ref(false);
watch(
  () => props.plugin.icon_url,
  () => {
    brokenIcon.value = false;
  },
);
const subscribed = computed(
  () =>
    subscriptions.get(props.plugin.plugin_id) ?? props.plugin.viewer_has_liked,
);
const author = computed(
  () =>
    props.plugin.owner_display_name ||
    props.plugin.owner_login ||
    props.plugin.owner_id,
);
const tags = computed(() => [
  ...(props.plugin.categories || []).slice(0, 1).map(categoryLabel),
  ...(props.plugin.tags || []).slice(0, 2),
]);
</script>
<template>
  <CatalogListing
    v-if="number !== undefined"
    :to="`/plugin/${encodeURIComponent(plugin.plugin_id)}`"
    :number="number" :lead="lead" :compact="compact"
    :title="plugin.display_name || plugin.plugin_id"
    :description="plugin.summary" :author="author" :icon="plugin.icon_url"
    :version="plugin.latest_version" :labels="tags" :source="trustLevelLabel(plugin.trust_level)"
    :categories="plugin.categories" :tags="plugin.tags"
  >
      <span v-market-tooltip="'下载次数'"
        ><AppIcon name="download" :size="13" />{{
          formatNumber(plugin.downloads_count)
        }}</span
      ><span
        v-if="plugin.rating_count"
        class="plugin-card-rating"
        v-market-tooltip="`${plugin.rating_count} 人评分`"
        >★ {{ Number(plugin.rating_avg || 0).toFixed(1) }}</span
      ><span :class="{ subscribed }" v-market-tooltip="'订阅人数'"
        ><AppIcon name="bookmark" :size="13" />{{
          formatNumber(plugin.likes_count)
        }}</span
      ><span v-if="plugin.comments_count > 0" v-market-tooltip="'评论数量'"
        ><AppIcon name="comment" :size="13" />{{
          formatNumber(plugin.comments_count)
        }}</span
      ><time :datetime="plugin.updated_at">{{
        formatRelative(plugin.updated_at)
      }}</time>
  </CatalogListing>
  <router-link v-else
    class="plugin-card"
    :class="{ 'is-featured': featured }"
    :to="`/plugin/${encodeURIComponent(plugin.plugin_id)}`"
  >
    <div class="plugin-card-top">
      <div class="plugin-card-icon">
        <img
          v-if="plugin.icon_url && !brokenIcon"
          :src="plugin.icon_url"
          alt=""
          loading="lazy"
          @error="brokenIcon = true"
        /><span v-else>{{
          (plugin.display_name || plugin.plugin_id).trim()[0]?.toUpperCase() ||
          'P'
        }}</span>
      </div>
      <span class="plugin-card-trust" :class="`trust-${plugin.trust_level}`"
        ><i></i>{{ trustLevelLabel(plugin.trust_level) }}</span
      ><span class="plugin-card-arrow" aria-hidden="true">↗</span>
    </div>
    <div class="plugin-card-heading">
      <h3>{{ plugin.display_name || plugin.plugin_id }}</h3>
      <span v-if="plugin.latest_version">v{{ plugin.latest_version }}</span>
    </div>
    <span class="plugin-card-author">{{ author }}</span>
    <p class="plugin-card-summary">
      {{ plugin.summary || '探索这个插件，为 MoFox 添加更多可能。' }}
    </p>
    <div class="plugin-card-tags">
      <span v-for="(tag, i) in tags" :key="`${i}-${tag}`">{{ tag }}</span>
    </div>
    <div class="plugin-card-footer">
      <span v-market-tooltip="'下载次数'"
        ><AppIcon name="download" :size="13" />{{
          formatNumber(plugin.downloads_count)
        }}</span
      ><span
        v-if="plugin.rating_count"
        class="plugin-card-rating"
        v-market-tooltip="`${plugin.rating_count} 人评分`"
        >★ {{ Number(plugin.rating_avg || 0).toFixed(1) }}</span
      ><span :class="{ subscribed }" v-market-tooltip="'订阅人数'"
        ><AppIcon name="bookmark" :size="13" />{{
          formatNumber(plugin.likes_count)
        }}</span
      ><span v-if="plugin.comments_count > 0" v-market-tooltip="'评论数量'"
        ><AppIcon name="comment" :size="13" />{{
          formatNumber(plugin.comments_count)
        }}</span
      ><time :datetime="plugin.updated_at">{{
        formatRelative(plugin.updated_at)
      }}</time>
    </div>
  </router-link>
</template>
<style scoped>
.plugin-card {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 100%;
  padding: 24px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 3px;
  color: var(--ink-900);
  transition:
    border-color var(--dur-base),
    transform var(--dur-base);
  text-decoration: none;
  overflow: hidden;
}
.plugin-card:before {
  content: '';
  position: absolute;
  top: -1px;
  left: -1px;
  width: 14px;
  height: 14px;
  border-top: 2px solid var(--blue-500);
  border-left: 2px solid var(--blue-500);
  opacity: 0;
  transition: opacity var(--dur-base);
}
.plugin-card:hover {
  border-color: var(--blue-300);
  transform: translateY(-3px);
  color: var(--ink-900);
}
.plugin-card:hover:before,
.plugin-card.is-featured:before {
  opacity: 1;
}
.plugin-card:focus-visible {
  outline: 3px solid var(--blue-300);
  outline-offset: 3px;
}
.plugin-card-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 22px;
}
.plugin-card-icon {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  flex: none;
  border: 1px solid var(--blue-200);
  background: var(--blue-50);
  color: var(--blue-700);
  font-size: 24px;
  font-weight: 650;
  overflow: hidden;
  border-radius: 3px;
}
.plugin-card-icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.plugin-card-trust {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--ink-500);
  margin-left: auto;
  font-size: 11px;
}
.plugin-card-trust i {
  width: 4px;
  height: 4px;
  background: var(--ink-300);
}
.plugin-card-trust.trust-official,
.plugin-card-trust.trust-verified {
  color: var(--blue-700);
}
.plugin-card-trust.trust-official i,
.plugin-card-trust.trust-verified i {
  background: var(--blue-500);
}
.plugin-card-arrow {
  font-size: 20px;
  line-height: 1;
  color: var(--ink-300);
  padding-left: 4px;
}
.plugin-card-heading {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.plugin-card-heading h3 {
  font: 650 17px/1.4 var(--font-sans);
  margin: 0;
  overflow-wrap: anywhere;
}
.plugin-card-heading > span {
  font: 10px var(--font-mono);
  color: var(--ink-500);
}
.plugin-card-author {
  font-size: 11px;
  color: var(--ink-500);
  margin-top: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.plugin-card-summary {
  font-size: 13px;
  line-height: 1.8;
  color: var(--ink-500);
  min-height: 46px;
  margin: 17px 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.plugin-card-tags {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
  min-height: 24px;
  margin-bottom: 22px;
}
.plugin-card-tags span {
  font-size: 10px;
  padding: 3px 7px;
  border: 1px solid var(--line-soft);
  background: var(--surface-soft);
  color: var(--ink-500);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.plugin-card-footer {
  margin-top: auto;
  display: flex;
  align-items: center;
  gap: 10px 12px;
  flex-wrap: wrap;
  border-top: 1px solid var(--line-soft);
  padding-top: 15px;
  color: var(--ink-500);
  font: 11px var(--font-mono);
}
.plugin-card-footer > span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
}
.plugin-card-footer time {
  margin-left: auto;
  white-space: nowrap;
  font-size: 10px;
}
.plugin-card-rating {
  color: var(--warning-ink);
}
.subscribed {
  color: var(--blue-700);
}
@media (prefers-reduced-motion: reduce) {
  .plugin-card:hover {
    transform: none;
  }
}
:global(:root[data-reduced-motion='reduce'] .plugin-card:hover) {
  transform: none;
}
</style>
