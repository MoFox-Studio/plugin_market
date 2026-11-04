<script setup lang="ts">
import { computed, ref } from 'vue';
import type { Plugin } from '@/types';
import EditionArtwork from '../EditionArtwork.vue';
import { useMarketPointerReveal } from '@/composables/useMarketPointerReveal';
import { folios } from './folioCatalogue';

const props = defineProps<{ plugin: Plugin; index: number }>();
const art = ref<HTMLElement>();
const plate = computed(() => folios[props.index]);
const number = computed(() => String(props.index + 1).padStart(2, '0'));
useMarketPointerReveal((pointer) => {
  const el = art.value;
  if (!el) return;
  if (pointer.active && pointer.local) {
    const box = el.getBoundingClientRect();
    if (
      box.width &&
      box.height &&
      pointer.x >= box.left &&
      pointer.x <= box.right &&
      pointer.y >= box.top &&
      pointer.y <= box.bottom
    ) {
      el.style.setProperty('--reveal-x', pointer.x - box.left + 'px');
      el.style.setProperty('--reveal-y', pointer.y - box.top + 'px');
      el.style.setProperty('--reveal-radius', pointer.radius + 'px');
      el.classList.add('is-revealing');
      return;
    }
  }
  el.classList.remove('is-revealing');
});
</script>

<template>
  <div class="folio-column">
    <div
      ref="art"
      class="spotlight-art"
      data-pointer-reveal-local
      :data-plate="plate.id"
      @pointerleave="art?.classList.remove('is-revealing')"
    >
      <div class="print-sheet">
        <div class="running-line">
          <span>社区插件选刊</span><span>PLATE {{ number }} / 20</span>
        </div>
        <div class="print-masthead" lang="en">MoFox Gazette</div>
        <div class="plate-edition">
          <span>精选图版</span><i>✦</i><span>社区出品</span>
        </div>
        <div class="front-scene">
          <svg viewBox="0 0 320 200" role="img" :aria-label="plate.title">
            <use :href="plate.front" width="320" height="200" />
          </svg>
          <div class="specimen">
            <EditionArtwork
              :icon="plugin.icon_url"
              :categories="plugin.categories"
              :tags="plugin.tags"
            />
          </div>
        </div>
        <div class="plate-caption">
          <i lang="en">Fig. {{ number }}</i
          ><b>{{ plate.title }}</b>
        </div>
      </div>
      <div class="spotlight-reveal" aria-hidden="true">
        <div class="running-line">
          <span>背印藏书票</span><span>EX LIBRIS · {{ number }}</span>
        </div>
        <div class="back-title">
          <i lang="en">Verso</i><b>{{ plate.reverse }}</b>
        </div>
        <svg
          class="back-scene"
          viewBox="0 0 320 200"
          role="img"
          :aria-label="plate.reverse"
        >
          <use :href="plate.back" width="320" height="200" />
        </svg>
        <div class="proof-byline">
          <span>{{
            plugin.owner_display_name || plugin.owner_login || plugin.owner_id
          }}</span
          ><small>{{
            plugin.latest_version
              ? 'v' + plugin.latest_version
              : plugin.plugin_id
          }}</small>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.folio-column {
  display: flex;
  min-width: 0;
  flex-direction: column;
  border-right: 1px solid var(--line-strong);
}
.spotlight-art {
  position: relative;
  display: grid;
  flex: 1;
  min-width: 0;
  isolation: isolate;
  overflow: hidden;
  color: var(--ink-900);
  background: var(--paper);
}
.print-sheet,
.spotlight-reveal {
  padding: 15px clamp(14px, 1.9vw, 29px);
  display: grid;
  min-width: 0;
}
.print-sheet {
  grid-template-rows: auto auto auto minmax(118px, 1fr) auto;
  background-image: radial-gradient(var(--line) 0.55px, transparent 0.8px);
  background-size: 4px 4px;
}
.running-line,
.plate-edition,
.proof-byline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font: 9px/1.4 var(--font-mono);
  letter-spacing: 0.1em;
}
.running-line {
  padding-bottom: 6px;
  border-bottom: 3px double currentColor;
}
.print-masthead {
  padding: 8px 0;
  font: 800 clamp(29px, 4.1vw, 63px) / 1 var(--font-editorial);
  letter-spacing: -0.06em;
  text-align: center;
}
.plate-edition {
  padding: 3px 0;
  border-block: 1px solid var(--line-strong);
  color: var(--ink-500);
}
.plate-edition i {
  color: var(--blue-700);
}
.front-scene {
  display: grid;
  grid-template-columns: minmax(0, 1fr) clamp(48px, 5.8vw, 78px);
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  color: var(--blue-900);
}
.front-scene > svg {
  width: 100%;
  height: 100%;
  max-height: 202px;
  min-height: 100px;
}
.specimen {
  display: grid;
  place-items: center;
  aspect-ratio: 1;
  padding: 5px;
  border: 3px double var(--line-strong);
  background: var(--surface);
}
.specimen :deep(.edition-art-icon),
.specimen :deep(.edition-engraving) {
  width: 100%;
  max-height: 64px;
}
.specimen :deep(.edition-engraving small) {
  font-size: 8px;
}
.plate-caption {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding-top: 8px;
  border-top: 3px double var(--ink-500);
}
.plate-caption i {
  color: var(--blue-700);
  font: 19px/1 var(--font-script);
}
.plate-caption b {
  font: 800 20px/1.3 var(--font-editorial);
}
.spotlight-reveal {
  position: absolute;
  inset: 0;
  z-index: 1;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  gap: 5px;
  color: var(--paper);
  background: var(--blue-900);
  background-image: repeating-linear-gradient(
    135deg,
    transparent 0 9px,
    color-mix(in srgb, var(--paper) 6%, transparent) 9px 10px
  );
  clip-path: circle(0 at var(--reveal-x, 0px) var(--reveal-y, 0px));
  pointer-events: none;
}
.is-revealing .spotlight-reveal {
  clip-path: circle(
    var(--reveal-radius, 110px) at var(--reveal-x) var(--reveal-y)
  );
}
.back-title {
  display: flex;
  align-items: baseline;
  gap: 14px;
  padding: 4px 0;
}
.back-title i {
  font: 30px/1 var(--font-script);
}
.back-title b {
  font: 800 20px/1.2 var(--font-editorial);
}
.back-scene {
  display: block;
  width: 100%;
  height: 100%;
  min-height: 0;
}
.proof-byline {
  padding-top: 6px;
  border-top: 3px double currentColor;
}
.proof-byline span {
  font: italic 16px/1.3 var(--font-reading);
}
@media (max-width: 600px) {
  .folio-column {
    border-right: 0;
    border-bottom: 1px solid var(--line-strong);
  }
  .front-scene > svg {
    max-height: 138px;
  }
}
</style>
