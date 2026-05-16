<script setup lang="ts">
import { computed } from 'vue'
import { categoryLabel } from '@/utils/format'
import type { Plugin } from '@/types'

interface CategoryItem {
  key: string
  label: string
  en: string
  count: number
  tone: 'coral' | 'lemon' | 'mint' | 'plum' | ''
}

const props = defineProps<{
  preview: Record<string, Plugin[]>
}>()

const TONE_ORDER: Array<CategoryItem['tone']> = ['coral', 'lemon', 'mint', 'plum']

const EN_FALLBACK: Record<string, string> = {
  core: 'CORE',
  ops: 'OPS',
  fun: 'FUN',
  tools: 'TOOLS',
  utility: 'UTILITY',
  game: 'GAME',
  social: 'SOCIAL',
  ai: 'AI',
  network: 'NETWORK',
}

const items = computed<CategoryItem[]>(() => {
  const entries = Object.entries(props.preview).slice(0, 6)
  return entries.map(([key, plugins], idx) => ({
    key,
    label: categoryLabel(key),
    en: EN_FALLBACK[key.toLowerCase()] || key.toUpperCase(),
    count: plugins.length,
    tone: TONE_ORDER[idx % TONE_ORDER.length],
  }))
})
</script>

<template>
  <div class="cat-jump" v-if="items.length">
    <router-link
      v-for="item in items"
      :key="item.key"
      class="cat-card"
      :data-tone="item.tone"
      :to="{ name: 'market', query: { category: item.key } }"
    >
      <div>
        <div class="name">{{ item.label }}</div>
        <div class="en">{{ item.en }}</div>
      </div>
      <div class="count">{{ item.count }}<small>plugins</small></div>
    </router-link>
  </div>
</template>

<style scoped>
.cat-jump {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-3);
}

.cat-card {
  position: relative;
  overflow: hidden;
  padding: var(--space-6) var(--space-5);
  border-radius: var(--radius-md);
  border: 1.5px solid var(--line);
  background: var(--surface);
  display: flex; flex-direction: column; justify-content: space-between;
  min-height: 138px;
  color: inherit;
  transition: transform var(--dur-base) var(--ease-emphasized), border-color var(--dur-base), box-shadow var(--dur-base);
}
.cat-card::before {
  content: ""; position: absolute; inset: 0;
  background: var(--halftone);
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--dur-base);
}
.cat-card:hover {
  border-color: var(--ink-900);
  transform: translate(-2px, -2px);
  box-shadow: var(--shadow-poster);
}
.cat-card:hover::before { opacity: 0.12; }

.cat-card .name {
  font-family: var(--font-display); font-weight: 900; font-size: 22px;
  color: var(--ink-900);
  line-height: 1.15;
  margin-bottom: 4px;
}
.cat-card .en {
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 11.5px; color: var(--ink-500);
}
.cat-card .count {
  align-self: flex-end;
  font-family: var(--font-brand); font-size: 32px;
  letter-spacing: 0.04em;
  color: var(--blue-700);
  line-height: 1;
}
.cat-card .count small {
  font-family: var(--font-mono); font-size: 11px;
  color: var(--ink-500); font-weight: 400;
  margin-left: 4px;
  letter-spacing: 0.06em;
}

.cat-card[data-tone="coral"] { background: var(--coral-soft); border-color: transparent; }
.cat-card[data-tone="coral"] .count { color: var(--danger-ink); }
.cat-card[data-tone="lemon"] { background: var(--lemon-soft); border-color: transparent; }
.cat-card[data-tone="lemon"] .count { color: var(--warning-ink); }
.cat-card[data-tone="mint"] { background: var(--mint-soft); border-color: transparent; }
.cat-card[data-tone="mint"] .count { color: var(--success-ink); }
.cat-card[data-tone="plum"] { background: var(--plum-soft); border-color: transparent; }
.cat-card[data-tone="plum"] .count { color: #5b3fd0; }
</style>
