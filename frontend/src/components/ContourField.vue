<script setup lang="ts">
import { onBeforeUnmount, ref, shallowRef, useId, watch } from 'vue';
import { SHEET_HEIGHT, useSurveyWorld } from '@/composables/useSurveyWorld';
import { surveyGeometry } from '@/composables/surveyGeometry';
import type { Contours } from '@/composables/surveyContours';

const baseStrip = ref<SVGSVGElement | null>(null);
const { sheets, viewBox, dimensions } = useSurveyWorld((position) => {
  if (baseStrip.value) baseStrip.value.style.transform = `translate3d(${position.x}px, ${position.y}px, 0)`;
});
const id = 'terrain-' + useId();
const geometry = shallowRef<Array<Contours & { index: number }>>([]);
const loader = surveyGeometry.subscribe(() => {
  geometry.value = sheets.value.flatMap(index => {
    const contours = surveyGeometry.get(index);
    return contours ? [{ index, ...contours }] : [];
  });
});
watch(sheets, indices => loader.setSheets(indices), { immediate: true });
onBeforeUnmount(loader.dispose);
</script>
<template>
  <div class="contour-field" aria-hidden="true">
    <div class="terrain-base">
      <svg ref="baseStrip" class="terrain-strip" :viewBox="viewBox" :style="dimensions" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-linecap="round">
        <defs>
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
.terrain-base {
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
  transform: translate3d(0, 0, 0);
  will-change: transform;
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
:global(:root[data-theme='dark'] .terrain-base) {
  opacity: 0.14;
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
}
</style>
