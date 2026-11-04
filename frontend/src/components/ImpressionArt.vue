<script setup lang="ts">
import type { Impression } from '@/composables/rareImpressions';
defineProps<{ print: Impression }>();
</script>
<template>
  <span
    v-if="print.mask"
    class="ink-portrait"
    role="img"
    :aria-label="print.alt"
    :style="{
      maskImage: 'url(' + print.source + ')',
      backgroundColor: print.ink,
    }"
  />
  <svg
    v-else
    viewBox="0 0 320 260"
    role="img"
    :aria-label="print.alt"
    :style="{ color: print.ink }"
  >
    <use :href="print.source" width="320" height="260" />
  </svg>
</template>
<style scoped>
.ink-portrait {
  display: block;
  width: 100%;
  aspect-ratio: 320 / 260;
  mask-size: contain;
  mask-repeat: no-repeat;
  mask-position: center;
}
</style>
