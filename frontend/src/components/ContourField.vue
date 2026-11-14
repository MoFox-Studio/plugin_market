<script setup lang="ts">
import { computed, useId } from 'vue';
import { SHEET_HEIGHT, useSurveyWorld } from '@/composables/useSurveyWorld';
import { surveyContours } from '@/composables/surveyContours';

const { sheets, viewBox, dimensions } = useSurveyWorld();
const id = 'terrain-' + useId();
const geometry = computed(() => sheets.value.map(index => ({ index, ...surveyContours(index) })));
</script>
<template>
  <div class="contour-field" aria-hidden="true">
    <div v-for="layer in ['base', 'reveal']" :key="layer" :class="`terrain-${layer}`">
      <svg class="terrain-strip" :viewBox="viewBox" :style="dimensions" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-linecap="round">
        <defs v-if="layer === 'base'">
          <g v-for="sheet in geometry" :id="`${id}-${sheet.index}`" :key="sheet.index">
            <path :d="sheet.minor" stroke-width="0.72" opacity="0.58" vector-effect="non-scaling-stroke" />
            <path :d="sheet.major" stroke-width="1.1" opacity="0.9" vector-effect="non-scaling-stroke" />
          </g>
        </defs>
        <use v-for="(sheet, i) in sheets" :key="sheet" :href="`#${id}-${sheet}`" :transform="`translate(0 ${i * SHEET_HEIGHT})`" :data-map-sheet="sheet" />
      </svg>
    </div>
  </div>
</template>
<style scoped>
.contour-field {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
  contain: strict;
}
.terrain-base,
.terrain-reveal {
  position: absolute;
  inset: 0;
  overflow: hidden;
  color: var(--blue-600);
}
.terrain-strip {
  position: absolute;
  top: 0;
  left: 0;
  max-width: none;
  transform: translate3d(var(--survey-sheet-x, 0px), var(--survey-sheet-y, 0px), 0);
}
.terrain-base {
  opacity: 0.23;
  mask-image: linear-gradient(
    100deg,
    transparent 0%,
    transparent 46%,
    rgba(0, 0, 0, 0.2) 57%,
    black 76%
  );
}
.terrain-reveal {
  opacity: calc(var(--market-pointer-active, 0) * 0.2);
  mask-image: radial-gradient(
    circle var(--market-pointer-radius, 110px) at
      var(--market-pointer-x, -200px) var(--market-pointer-y, -200px),
    black 20%,
    transparent 100%
  );
}
:global(:root[data-theme='dark'] .terrain-base) {
  opacity: 0.14;
}
:global(:root[data-theme='dark'] .terrain-reveal) {
  opacity: calc(var(--market-pointer-active, 0) * 0.13);
}
@media (max-width: 760px) {
  .terrain-base {
    opacity: 0.18;
    mask-image: linear-gradient(
      100deg,
      transparent 0%,
      transparent 59%,
      black 87%
    );
  }
  .terrain-reveal {
    display: none;
  }
}
@media (prefers-reduced-motion: reduce), (pointer: coarse) {
  .terrain-reveal {
    display: none;
  }
}
</style>
