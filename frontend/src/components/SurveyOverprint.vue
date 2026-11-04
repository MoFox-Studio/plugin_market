<script setup lang="ts">
import { computed, inject } from 'vue';
import { routeLocationKey } from 'vue-router';
import { SHEET_HEIGHT, useSurveyWorld } from '@/composables/useSurveyWorld';
import plates from '@/assets/survey-plates.svg?no-inline';
import miniatures from '@/assets/survey-miniatures.svg?no-inline';
import { surveyMiniatures } from '@/composables/surveyMiniatures';

const route = inject(routeLocationKey, null);
const { sheets, dimensions, viewBox } = useSurveyWorld();
const editions = {
  home: { symbol: 'pass', code: 'RIDGE', x: 1110, y: 285 },
  catalog: { symbol: 'chart', code: 'ATLAS', x: 1050, y: 250 },
  detail: { symbol: 'proof', code: 'PROOF', x: 1145, y: 335 },
  field: { symbol: 'relay', code: 'RELAY', x: 1090, y: 275 },
} as const;
const edition = computed(() => {
  switch (route?.name) {
    case 'home': return editions.home;
    case 'market': case 'skills': return editions.catalog;
    case 'plugin': case 'skill': case 'author': return editions.detail;
    default: return editions.field;
  }
});
function variation(sheet: number, salt: number) {
  let value = Math.imul(sheet + 1, 0x45d9f3b) ^ salt;
  value = Math.imul(value ^ (value >>> 16), 0x45d9f3b);
  return ((value ^ (value >>> 16)) >>> 0) / 0xffffffff;
}
const symbols = ['pass', 'chart', 'proof', 'relay'];
const marks = computed(() => sheets.value.map((sheet, i) => {
  const theme = edition.value;
  const x = sheet ? Math.round(570 + 800 * variation(sheet, 31)) : theme.x;
  const y = sheet ? Math.round(140 + 240 * variation(sheet, 57)) : theme.y;
  return {
    sheet, x, y, top: i * SHEET_HEIGHT,
    miniatures: surveyMiniatures(sheet, theme.code),
    symbol: sheet % 3 === 0 ? theme.symbol : symbols[Math.floor(variation(sheet, 97) * symbols.length) % symbols.length],
    east: Math.round(700 + 600 * variation(sheet, 139)),
    north: 475 + Math.round(75 * variation(sheet, 73)),
    label: theme.code + ' / ' + String(sheet + 1).padStart(3, '0'),
  };
}));
</script>
<template>
  <div class="survey-ink-window" aria-hidden="true" :data-edition="edition.code">
    <svg class="survey-ink-sheet" :viewBox="viewBox" :style="dimensions" fill="none">
      <g v-for="mark in marks" :key="mark.sheet" :transform="`translate(0 ${mark.top})`">
        <use class="survey-discovery" :href="`${plates}#${mark.symbol}`" :x="mark.x - 110" :y="mark.y - 58" width="220" height="116" :data-map-x="mark.x" :data-map-y="mark.sheet * SHEET_HEIGHT + mark.y" />
        <g v-for="site in mark.miniatures" :key="site.id" :transform="`translate(${site.x} ${site.y})`">
          <use class="survey-miniature" :href="`${miniatures}#${site.id}`" width="120" height="77" />
          <path d="M2 67v8h12m96-69h8v8" fill="none" stroke="currentColor" stroke-width=".8"/>
          <text x="90" y="76" text-anchor="end" fill="currentColor" font-family="monospace" font-size="6" letter-spacing="1.2">FIG. {{ site.number }}</text>
        </g>
        <g :transform="`translate(${mark.east} ${mark.north})`">
          <path d="M-53 0h106m-104-6v12m9-8v4m9-4v4m9-6v8m9-6v4m9-4v4m9-8v12m9-8v4m9-4v4m9-6v8m9-6v4m9-4v4" stroke="currentColor" stroke-width="0.9" />
          <text x="-52" y="17" fill="currentColor" font-family="monospace" font-size="7" letter-spacing="1.2">{{ mark.label }}</text>
        </g>
      </g>
    </svg>
  </div>
</template>
<style scoped>
.survey-ink-window {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  clip-path: circle(var(--market-pointer-radius, 0px) at var(--market-pointer-x, -200px) var(--market-pointer-y, -200px));
  color: var(--blue-700);
  opacity: .66;
}
.survey-ink-sheet {
  position: absolute;
  top: 0;
  left: 0;
  max-width: none;
  transform: translate3d(var(--survey-sheet-x, 0px), var(--survey-sheet-y, 0px), 0);
}
:global(.market-pointer-reveal[data-surface='paper'] .survey-ink-window) { opacity: .19; }
:global(.market-pointer-reveal[data-surface='control'] .survey-ink-window) { visibility: hidden; }
:global(:root[data-theme='dark'] .survey-ink-window) { color: var(--blue-500); }
</style>
