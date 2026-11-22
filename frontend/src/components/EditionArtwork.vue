<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import illustrations from '@/assets/edition-illustrations.svg?no-inline';

const props = defineProps<{
  icon?: string | null;
  categories?: string[] | null;
  tags?: string[] | null;
  loading?: 'lazy' | 'eager';
}>();
const failed = ref(false);
watch(() => props.icon, () => { failed.value = false; });

const plates = new Map([
  ['fun', 'fun'], ['game', 'fun'], ['chat', 'chat'],
  ['vision', 'vision'], ['image', 'vision'],
  ['moderation', 'moderation'], ['information', 'information'],
]);
const illustration = computed(() => {
  const tags = props.tags?.map(tag => tag.toLowerCase()) || [];
  if (tags.includes('sticker')) return 'sticker';
  if (tags.includes('music')) return 'music';
  return plates.get(props.categories?.[0]?.toLowerCase() || '') || 'tool';
});

function onImageError(event: Event) {
  if ((event.target as HTMLImageElement).getAttribute('src') === props.icon) {
    failed.value = true;
  }
}
</script>

<template>
  <img v-if="icon && !failed" :key="icon" class="edition-art-icon" :src="icon" alt="" :loading="loading" @error="onImageError" />
  <span v-else class="edition-engraving" role="img" aria-label="题材插图">
    <svg viewBox="0 0 280 190" aria-hidden="true">
      <use :href="illustrations + '#' + illustration" width="280" height="190" />
    </svg>
    <small aria-hidden="true">题材插图</small>
  </span>
</template>

<style scoped>
.edition-art-icon { display: block; max-width: 100%; object-fit: contain; }
.edition-engraving { display: grid; justify-items: center; align-content: center; min-width: 0; --plate-ground: var(--surface-soft); }
.edition-engraving svg { display: block; width: 100%; height: auto; min-width: 0; }
.edition-engraving small { font: 10px/1.4 var(--font-sans); letter-spacing: .05em; color: var(--ink-500); }
</style>
