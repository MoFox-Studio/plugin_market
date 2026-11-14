<script setup lang="ts">
import type { Impression } from '@/composables/rareImpressions';
defineProps<{ print: Impression }>();
</script>
<template>
  <div
    v-if="print.mask"
    class="portrait-plate"
    role="img"
    :aria-label="print.alt"
    :style="{ color: print.ink }"
  >
    <svg class="portrait-frame" viewBox="0 0 640 480" aria-hidden="true">
      <g fill="none" stroke="currentColor" opacity=".38">
        <path d="M184 82C224 20 420 18 461 80M172 81C213 4 430 3 473 79M181 396c55 63 214 63 269 0M175 408c66 67 215 65 280-3" stroke-width=".7" />
        <path d="m148 170-16 70 20 70m340-137 17 67-20 70M138 195l7 42-9 43m366-86-8 46 7 40" stroke-width="1.4" />
        <path d="M107 84h36m-18-18v36m386 274h36m-18-18v36" stroke-width=".8" />
        <circle cx="125" cy="84" r="10" /><circle cx="529" cy="376" r="10" />
      </g>
    </svg>
    <span class="ink-portrait" :style="{ maskImage: 'url(' + print.source + ')', backgroundColor: print.ink }" />
  </div>
  <svg
    v-else
    class="impression-vector"
    viewBox="0 0 640 480"
    role="img"
    :aria-label="print.alt"
    :style="{ color: print.ink }"
  >
    <use :href="print.source" width="640" height="480" />
  </svg>
</template>
<style scoped>
.impression-vector {
  --impression-shadow: var(--ink-900);
}
:global(:root[data-theme='dark']) .impression-vector {
  --impression-shadow: var(--paper);
}
.portrait-plate {
  display: block;
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
}
.portrait-frame {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.ink-portrait {
  display: block;
  position: absolute;
  inset: 3% 6%;
  mask-size: contain;
  mask-repeat: no-repeat;
  mask-position: center;
}
</style>
