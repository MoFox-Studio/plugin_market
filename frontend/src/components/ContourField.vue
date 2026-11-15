<script setup lang="ts">
import { onBeforeUnmount, ref, shallowRef, useId, watch } from 'vue';
import { SHEET_HEIGHT, useSurveyWorld } from '@/composables/useSurveyWorld';
import { surveyGeometry } from '@/composables/surveyGeometry';
import type { Contours } from '@/composables/surveyContours';
import { useMarketPointerReveal } from '@/composables/useMarketPointerReveal';

const baseStrip = ref<SVGSVGElement | null>(null);
const revealStrip = ref<SVGSVGElement | null>(null);
const revealWindow = ref<HTMLElement | null>(null);
let worldPosition = { x: 0, y: 0 };
let lensOrigin = { x: 0, y: 0 };
function paintRevealPosition() {
  if (revealStrip.value) revealStrip.value.style.transform = `translate3d(${worldPosition.x - lensOrigin.x}px, ${worldPosition.y - lensOrigin.y}px, 0)`;
}
const { sheets, viewBox, dimensions } = useSurveyWorld((position) => {
  worldPosition = position;
  if (baseStrip.value) baseStrip.value.style.transform = `translate3d(${position.x}px, ${position.y}px, 0)`;
  paintRevealPosition();
});
useMarketPointerReveal((pointer) => {
  const element = revealWindow.value;
  if (!element) return;
  element.style.setProperty('--market-pointer-active', pointer.active ? '1' : '0');
  if (!pointer.active) return;
  element.style.setProperty('--market-pointer-radius', `${pointer.radius}px`);
  const x = pointer.x - 112, y = pointer.y - 112;
  if (x !== lensOrigin.x || y !== lensOrigin.y) {
    lensOrigin = { x, y };
    element.style.transform = `translate3d(${x}px, ${y}px, 0)`;
    paintRevealPosition();
  }
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
    <div v-for="layer in ['base', 'reveal']" :key="layer" :ref="el => { if (layer === 'reveal') revealWindow = el as HTMLElement; }" :class="`terrain-${layer}`">
      <svg :ref="el => { if (layer === 'base') baseStrip = el as SVGSVGElement; else revealStrip = el as SVGSVGElement; }" class="terrain-strip" :viewBox="viewBox" :style="dimensions" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-linecap="round">
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
.terrain-reveal {
  inset: auto;
  top: 0;
  left: 0;
  width: 224px;
  height: 224px;
  contain: strict;
  opacity: calc(var(--market-pointer-active, 0) * 0.2);
  mask-image: radial-gradient(
    circle var(--market-pointer-radius, 110px) at
      112px 112px,
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
