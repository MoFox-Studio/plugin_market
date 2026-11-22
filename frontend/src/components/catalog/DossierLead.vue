<script setup lang="ts">
import { categoryLabel, formatRelative } from '@/utils/format';
import EditionArtwork from '@/components/EditionArtwork.vue';
defineProps<{
  kind: string;
  title: string;
  identifier: string;
  summary?: string | null;
  icon?: string | null;
  author: string;
  authorId: string;
  updatedAt: string;
  version?: string | null;
  categories?: string[];
  tags?: string[];
  categoryRoute: 'market' | 'skills';
  note?: string;
  license?: string | null;
}>();
</script>

<template>
  <header class="dossier-lead">
    <div class="lead-text">
      <p class="lead-section">
        <span>{{ kind }}档案</span>
        <router-link v-for="category in categories || []" :key="category" :to="{ name: categoryRoute, query: { category } }">{{ categoryLabel(category) }}</router-link>
      </p>
      <h1>{{ title }}</h1>
      <p v-if="summary" class="lead-summary">{{ summary }}</p>
      <div class="lead-byline">
        <span>维护者 <router-link :to="{ name: 'author', params: { id: authorId } }">{{ author }}</router-link></span>
        <time :datetime="updatedAt">更新于 {{ formatRelative(updatedAt) }}</time>
        <span v-if="license">{{ license }}</span>
      </div>
      <slot name="actions" />
    </div>
    <figure class="lead-plate">
      <div class="lead-specimen">
        <EditionArtwork :icon="icon" :categories="categories" :tags="tags" />
      </div>
      <figcaption>
        <code>{{ identifier }}</code>
        <span v-if="version" class="catalog-version">v{{ version }}</span>
        <small v-if="note">{{ note }}</small>
      </figcaption>
    </figure>
  </header>
</template>

<style scoped>
.dossier-lead { display: grid; grid-template-columns: minmax(0,1fr) minmax(140px,.29fr); gap: clamp(24px, 5vw, 76px); align-items: center; padding: 8px 0 28px; border-bottom: 3px double var(--ink-500); }
.lead-text { min-width: 0; }
.lead-section { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 12px; margin: 0 0 13px; color: var(--ink-500); font-size: 12px; }
.lead-section>span { color: var(--blue-700); letter-spacing: .12em; }
.lead-section a { text-decoration: underline; text-underline-offset: 3px; }
.lead-text h1 { margin: 0; font: 800 clamp(39px, 5.3vw, 74px)/1.13 var(--font-editorial); overflow-wrap: anywhere; color: var(--ink-900); }
.lead-summary { max-width: 52ch; margin: 18px 0; color: var(--ink-700); font: 400 clamp(17px, 1.8vw, 23px)/1.7 var(--font-reading); overflow-wrap: anywhere; }
.lead-byline { display: flex; flex-wrap: wrap; gap: 8px 22px; margin-top: 18px; font-size: 12px; color: var(--ink-500); }
.lead-byline a { margin-left: 5px; font-weight: 650; color: var(--blue-700); overflow-wrap: anywhere; }
.lead-plate { margin: 0; min-width: 0; }
.lead-specimen { display: grid; place-items: center; min-height: 150px; padding: 18px; background: repeating-linear-gradient(135deg, transparent 0 8px, var(--line-soft) 8px 9px), var(--surface-soft); }
.lead-specimen>.edition-art-icon { width: min(100%, 96px); max-height: 120px; background: var(--surface); }
.lead-specimen>.edition-engraving { width: min(100%, 230px); background: var(--surface-soft); color: var(--blue-700); }
.lead-plate figcaption { display: flex; flex-wrap: wrap; gap: 5px 8px; align-items: baseline; margin-top: 7px; font-size: 11px; color: var(--ink-500); overflow-wrap: anywhere; }
.lead-plate code { background: none; padding: 0; font-size: 10px; }
.lead-plate small { flex-basis: 100%; font-size: 10px; }
@media(max-width:660px) {
  .dossier-lead { grid-template-columns: minmax(0,1fr) 80px; gap: 13px; align-items: start; padding-bottom: 20px; }
  .lead-text h1 { font-size: clamp(31px, 8vw, 44px); }
  .lead-summary { font-size: 15px; margin: 12px 0; }
  .lead-specimen { min-height: 80px; padding: 12px; }
  .lead-specimen>.edition-art-icon { max-width: 54px; }
  .lead-byline { font-size: 11px; gap: 6px 12px; margin-top: 12px; }
  .lead-section { margin-bottom: 7px; }
}
</style>
