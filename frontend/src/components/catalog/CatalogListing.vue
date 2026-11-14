<script setup lang="ts">
import { ref, watch } from 'vue';
import type { RouteLocationRaw } from 'vue-router';
import EditionArtwork from '@/components/EditionArtwork.vue';
const props = defineProps<{
  to: RouteLocationRaw;
  number: number;
  title: string;
  description?: string | null;
  author: string;
  icon?: string | null;
  version?: string | null;
  labels?: string[];
  categories?: string[] | null;
  tags?: string[] | null;
  source?: string;
  lead?: boolean;
  compact?: boolean;
}>();
const broken = ref(false);
watch(() => props.icon, () => { broken.value = false; });
</script>

<template>
  <router-link :to="to" class="edition-entry" :class="{ 'is-lead': lead, 'is-compact': compact }">
    <figure class="entry-figure">
      <span class="entry-number" :aria-label="`目录序号 ${number}`">{{ String(number).padStart(2, '0') }}</span>
      <EditionArtwork v-if="lead" class="entry-artwork" :icon="icon" :categories="categories" :tags="tags" loading="lazy" />
      <div v-else class="entry-specimen">
        <img v-if="icon && !broken" :src="icon" alt="" loading="lazy" @error="broken = true" />
        <span v-else aria-hidden="true">{{ title.trim()[0]?.toUpperCase() }}</span>
      </div>
    </figure>
    <div class="entry-copy">
      <p class="entry-credit"><span v-if="source">{{ source }} · </span>{{ author }}</p>
      <h3>{{ title }}</h3>
      <p class="entry-description">{{ description || '作者尚未填写简介。' }}</p>
      <p v-if="version || labels?.length" class="entry-reference">
        <code v-if="version">v{{ version }}</code>
        <span v-if="labels?.length">{{ labels.join(' · ') }}</span>
      </p>
      <footer class="entry-edition"><slot /></footer>
    </div>
  </router-link>
</template>

<style scoped>
.edition-entry { display: grid; align-content: start; min-width: 0; padding: 20px 0; color: var(--ink-900); border-bottom: 1px solid var(--line); }
.entry-figure { display: flex; align-items: center; gap: 12px; margin: 0 0 12px; }
.entry-number { font: 400 17px/1 var(--font-reading); color: var(--blue-700); font-variant-numeric: tabular-nums; }
.entry-specimen { width: 30px; aspect-ratio: 1; display: grid; place-items: center; background: var(--surface-soft); color: var(--blue-700); font: 700 18px var(--font-editorial); }
.entry-specimen img { width: 100%; height: 100%; object-fit: contain; }
.entry-copy { min-width: 0; }
.entry-credit, .entry-reference, .entry-edition { font-size: 11px; line-height: 1.55; color: var(--ink-500); overflow-wrap: anywhere; }
.entry-credit { margin: 0 0 5px; }
.entry-copy h3 { margin: 0; font: 800 clamp(21px, 2vw, 30px)/1.3 var(--font-editorial); overflow-wrap: anywhere; }
.entry-description { margin: 10px 0; font: 400 14px/1.85 var(--font-reading); overflow-wrap: anywhere; }
.entry-reference, .entry-edition { display: flex; flex-wrap: wrap; gap: 5px 12px; }
.entry-reference { margin: 12px 0 0; }
.entry-reference code { background: none; padding: 0; }
.entry-edition { margin-top: 14px; }
.entry-edition :slotted(span) { display: inline-flex; align-items: center; gap: 4px; }
.edition-entry:hover h3, .edition-entry:focus-visible h3 { color: var(--blue-700); text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 4px; }
.is-lead { grid-column: 1 / -1; grid-template-columns: minmax(120px, .48fr) minmax(0, 1fr); align-items: center; gap: clamp(18px, 3vw, 36px); padding: 0 0 24px; }
.is-lead .entry-figure { position: relative; align-self: stretch; display: grid; place-items: center; min-height: 168px; margin: 0; padding: 32px 14px; background: repeating-linear-gradient(135deg, transparent 0 7px, var(--line-soft) 7px 8px), var(--surface-soft); }
.is-lead .entry-number { position: absolute; top: 12px; left: 14px; padding: 2px 4px; background: var(--surface-soft); }
.is-lead .entry-artwork.edition-art-icon { width: min(100%, 110px); max-height: 125px; background: var(--surface); outline: 5px solid var(--surface-soft); }
.is-lead .entry-artwork.edition-engraving { width: min(100%, 235px); color: var(--blue-700); background: var(--surface-soft); }
.is-lead h3 { font-size: clamp(28px, 3.2vw, 46px); }
.is-lead .entry-description { font-size: 16px; max-width: 55ch; }
.is-compact { grid-template-columns: 64px minmax(0, 1fr); gap: 15px; padding-block: 17px; }
.is-compact .entry-figure { align-self: start; margin-top: 3px; gap: 8px; }
.is-compact .entry-credit { margin: 0; }
.is-compact .entry-description { margin-block: 4px; }
.is-compact .entry-reference, .is-compact .entry-edition { margin-top: 6px; }
@media (max-width: 560px) {
  .is-lead { grid-template-columns: minmax(76px, .37fr) minmax(0, 1fr); gap: 14px; }
  .is-lead .entry-figure { min-height: 146px; }
  .is-lead .entry-artwork.edition-art-icon { max-width: 56px; }
  .is-lead h3 { font-size: 26px; }
  .is-lead .entry-description { font-size: 14px; }
  .is-compact { grid-template-columns: 44px minmax(0, 1fr); gap: 9px; }
  .is-compact .entry-figure { flex-direction: column; }
}
</style>
