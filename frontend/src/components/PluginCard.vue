<script setup lang="ts">
import { computed } from 'vue'
import { formatNumber, formatRelative, categoryLabel, starPercent } from '@/utils/format'
import { useSubscriptionStore } from '@/stores/subscriptions'
import type { Plugin } from '@/types'

const props = defineProps<{
  plugin: Plugin
  /** featured = 显示一条蓝色 FEATURED 飘带（用于 admin 推荐位） */
  featured?: boolean
}>()

const subStore = useSubscriptionStore()

const isLiked = computed(() => {
  const override = subStore.get(props.plugin.plugin_id)
  return override !== undefined ? override : props.plugin.viewer_has_liked
})

const tags = computed(() => [
  ...(props.plugin.categories || []).slice(0, 2).map((c: string) => ({ label: categoryLabel(c), raw: c, isCat: true })),
  ...(props.plugin.tags || []).slice(0, 3).map((t: string) => ({ label: t, raw: t, isCat: false })),
])

const author = computed(() =>
  props.plugin.owner_display_name || props.plugin.owner_login || props.plugin.owner_id,
)

const trustText = computed(() => {
  const map: Record<string, string> = { official: '公式', verified: '認定', community: '同人' }
  return map[props.plugin.trust_level] || props.plugin.trust_level
})
const trustZh = computed(() => {
  const map: Record<string, string> = { official: '官方', verified: '认证', community: '社区' }
  return map[props.plugin.trust_level] || props.plugin.trust_level
})

const palette = computed(() => {
  const id = props.plugin.plugin_id
  const tones = ['', 'coral', 'lemon', 'mint', 'plum'] as const
  let h = 0
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return tones[h % tones.length]
})
</script>

<template>
  <router-link
    class="card pcard-v2"
    :class="[{ 'is-featured': featured }, palette ? `palette-${palette}` : '']"
    :to="`/plugin/${encodeURIComponent(plugin.plugin_id)}`"
  >
    <div class="card-head">
      <div class="card-icon">
        <img v-if="plugin.icon_url" :src="plugin.icon_url" :alt="plugin.display_name">
        <template v-else>{{ (plugin.display_name || plugin.plugin_id || '?').trim()[0]?.toUpperCase() || '?' }}</template>
      </div>
      <div class="card-title-row">
        <h3 class="card-title">
          <span class="card-title-text">{{ plugin.display_name }}</span>
          <span :class="['badge', `trust-${plugin.trust_level}`]" :title="`${trustZh} (${trustText})`">
            {{ trustZh }}
          </span>
        </h3>
        <div class="card-slug">
          {{ plugin.plugin_id }}
          <template v-if="plugin.latest_version"> · <span class="card-version-chip">v{{ plugin.latest_version }}</span></template>
        </div>
        <div class="card-author">
          <img v-if="plugin.owner_avatar_url" :src="plugin.owner_avatar_url" :alt="author">
          <span>{{ author }}</span>
        </div>
      </div>
    </div>
    <p class="card-summary">{{ plugin.summary }}</p>
    <div class="card-tags">
      <span v-for="tag in tags" :key="tag.raw" :class="['tag', { cat: tag.isCat }]">
        {{ tag.isCat ? tag.label : `#${tag.label}` }}
      </span>
    </div>
    <div class="card-meta">
      <div class="card-stats">
        <span class="rating" v-if="plugin.rating_count > 0">
          <span class="stars" aria-hidden="true">
            ★★★★★
            <span class="fill" :style="{ width: starPercent(plugin.rating_avg) + '%' }">★★★★★</span>
          </span>
          <span>{{ plugin.rating_avg.toFixed(1) }}</span>
        </span>
        <span :class="['stat-item', { liked: isLiked }]">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1z"/></svg>
          <span>{{ formatNumber(plugin.likes_count) }}</span>
        </span>
        <span class="stat-item">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          <span>{{ formatNumber(plugin.downloads_count) }}</span>
        </span>
        <span class="stat-item" v-if="plugin.comments_count > 0">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          <span>{{ formatNumber(plugin.comments_count) }}</span>
        </span>
      </div>
      <span>{{ formatRelative(plugin.updated_at) }}</span>
    </div>
  </router-link>
</template>

<style scoped>
.pcard-v2 {
  text-decoration: none;
  color: inherit;
}

.pcard-v2 .badge {
  flex: 0 0 auto;
}
.pcard-v2 .badge small {
  display: none;
}
.pcard-v2 .badge:hover small,
.pcard-v2:hover .badge small {
  display: inline;
}

.pcard-v2 .card-icon { transition: transform var(--dur-base) var(--ease-pop); }
.pcard-v2:hover .card-icon { transform: rotate(-2deg) scale(1.05); }

.pcard-v2.palette-coral .card-icon { background: linear-gradient(135deg, var(--coral), #ff8a8d); color: #fff; }
.pcard-v2.palette-lemon .card-icon { background: linear-gradient(135deg, var(--lemon), #ffaa3a); color: var(--ink-900); }
.pcard-v2.palette-mint  .card-icon { background: linear-gradient(135deg, var(--mint), #28a585);  color: #fff; }
.pcard-v2.palette-plum  .card-icon { background: linear-gradient(135deg, var(--plum), #5a3fd9);  color: #fff; }
</style>
