<script setup lang="ts">
import { computed } from 'vue'
import { formatNumber, formatRelative, categoryLabel, starPercent } from '@/utils/format'

const props = defineProps({
  plugin: { type: Object, required: true },
})

const tags = computed(() => [
  ...(props.plugin.categories || []).slice(0, 2).map((c: string) => ({ label: categoryLabel(c), raw: c, isCat: true })),
  ...(props.plugin.tags || []).slice(0, 3).map((t: string) => ({ label: t, raw: t, isCat: false })),
])

const author = computed(() =>
  props.plugin.owner_display_name || props.plugin.owner_login || props.plugin.owner_id
)
</script>

<template>
  <router-link
    class="card"
    :to="`/plugin/${encodeURIComponent(plugin.plugin_id)}`"
  >
    <div class="card-head">
      <div class="card-icon">
        <img v-if="plugin.icon_url" :src="plugin.icon_url" alt="">
        <template v-else>{{ (plugin.display_name || plugin.plugin_id || '?').trim()[0]?.toUpperCase() || '?' }}</template>
      </div>
      <div class="card-title-row">
        <h3 class="card-title">
          <span class="card-title-text">{{ plugin.display_name }}</span>
          <span :class="['badge', `trust-${plugin.trust_level}`]">
            {{ ({ official: '官方', verified: '认证', community: '社区' } as Record<string, string>)[plugin.trust_level] || plugin.trust_level }}
          </span>
        </h3>
        <div class="card-slug">
          {{ plugin.plugin_id }}
          <template v-if="plugin.latest_version"> · <span class="card-version-chip">v{{ plugin.latest_version }}</span></template>
        </div>
        <div class="card-author">
          <img v-if="plugin.owner_avatar_url" :src="plugin.owner_avatar_url" alt="">
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
        <span class="rating">
          <span class="stars" aria-hidden="true">
            ★★★★★
            <span class="fill" :style="{ width: starPercent(plugin.rating_avg) + '%' }">★★★★★</span>
          </span>
          <span>{{ plugin.rating_avg.toFixed(1) }}</span>
        </span>
        <span :class="['stat-item', { liked: plugin.viewer_has_liked }]">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
          <span>{{ formatNumber(plugin.likes_count) }}</span>
        </span>
        <span class="stat-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          <span>{{ formatNumber(plugin.downloads_count) }}</span>
        </span>
        <span class="stat-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          <span>{{ formatNumber(plugin.comments_count) }}</span>
        </span>
      </div>
      <span>{{ formatRelative(plugin.updated_at) }}</span>
    </div>
  </router-link>
</template>
