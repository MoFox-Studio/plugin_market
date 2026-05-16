<script setup lang="ts">
import { computed } from 'vue'
import type { Plugin } from '@/types'
import { formatRelative } from '@/utils/format'

const props = defineProps<{
  items: Plugin[]
}>()

const palettes = ['', 'coral', 'lemon', 'mint', 'plum'] as const

const visible = computed(() => props.items.slice(0, 10))

function paletteOf(idx: number): string {
  return palettes[idx % palettes.length]
}

function isFreshPublish(plugin: Plugin): boolean {
  if (!plugin.created_at) return false
  return new Date(plugin.created_at).getTime() > Date.now() - 7 * 24 * 3600 * 1000
}
</script>

<template>
  <div class="latest-strip" v-if="visible.length">
    <router-link
      v-for="(plugin, idx) in visible"
      :key="plugin.plugin_id"
      :to="{ name: 'plugin', params: { id: plugin.plugin_id } }"
      class="strip-card"
    >
      <div class="head">
        <div :class="['ic', paletteOf(idx)]" aria-hidden="true">
          <img v-if="plugin.icon_url" :src="plugin.icon_url" :alt="plugin.display_name">
          <template v-else>{{ plugin.display_name[0]?.toUpperCase() || '?' }}</template>
        </div>
        <div class="text">
          <h4>{{ plugin.display_name }}</h4>
          <span class="v">{{ plugin.plugin_id }}</span>
        </div>
      </div>
      <p class="summary">{{ plugin.summary }}</p>
      <div class="meta">
        <span>v{{ plugin.latest_version || '-' }} · {{ formatRelative(plugin.latest_version_published_at || plugin.updated_at) }}</span>
        <span :class="['fresh', isFreshPublish(plugin) ? 'is-new' : 'is-upd']">
          {{ isFreshPublish(plugin) ? 'NEW' : 'UPD' }}
        </span>
      </div>
    </router-link>
  </div>
</template>

<style scoped>
.latest-strip {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: 240px;
  gap: var(--space-3);
  overflow-x: auto;
  padding: 4px 4px 14px;
  scroll-snap-type: x mandatory;
}

.strip-card {
  scroll-snap-align: start;
  display: grid; gap: 8px;
  padding: var(--space-3);
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  transition: transform var(--dur-fast) var(--ease-emphasized), border-color var(--dur-fast), box-shadow var(--dur-fast);
  color: inherit;
}
.strip-card:hover {
  border-color: var(--blue-500);
  transform: translate(-2px, -2px);
  box-shadow: var(--shadow-poster-soft);
}

.head { display: flex; align-items: center; gap: 10px; }
.ic {
  width: 40px; height: 40px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--blue-500), var(--blue-700));
  color: var(--ink-on-blue);
  display: grid; place-items: center;
  font-family: var(--font-display); font-weight: 800; font-size: 16px;
  flex: 0 0 auto;
  overflow: hidden;
}
.ic.coral { background: linear-gradient(135deg, var(--coral), #ff8a8d); color: #fff; }
.ic.lemon { background: linear-gradient(135deg, var(--lemon), #ffaa3a); color: var(--ink-900); }
.ic.mint  { background: linear-gradient(135deg, var(--mint), #28a585); color: #fff; }
.ic.plum  { background: linear-gradient(135deg, var(--plum), #5a3fd9); color: #fff; }
.ic img { width: 100%; height: 100%; object-fit: cover; }

.text { min-width: 0; display: grid; gap: 1px; }
.text h4 {
  margin: 0; font-size: 14px; font-weight: 700; color: var(--ink-900);
  line-height: 1.2;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.text .v {
  font-family: var(--font-mono); font-size: 11px; color: var(--ink-500);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.summary {
  margin: 0;
  font-size: 12.5px; color: var(--ink-700); line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}

.meta {
  display: flex; justify-content: space-between; align-items: center;
  font-family: var(--font-mono); font-size: 11px; color: var(--ink-500);
  margin-top: auto;
}
.fresh {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  font-family: var(--font-brand); letter-spacing: 0.06em;
  font-size: 10px; font-weight: 700;
}
.fresh.is-new { background: var(--lemon); color: var(--ink-900); }
.fresh.is-upd { background: var(--blue-100); color: var(--blue-700); }
</style>
