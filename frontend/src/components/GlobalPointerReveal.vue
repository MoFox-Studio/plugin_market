<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { useMarketPointerReveal } from '@/composables/useMarketPointerReveal';
import SurveyOverprint from './SurveyOverprint.vue';

const lens = ref<HTMLElement | null>(null);
const overprint = ref<InstanceType<typeof SurveyOverprint> | null>(null);
// CSS already hides this artwork on touch/reduced-motion devices. Do not build
// its external SVG use trees (and fetch every referenced atlas) in that mode.
const artworkEnabled = ref(false);
let artworkMedia: MediaQueryList | undefined;
let artworkPreference: MutationObserver | undefined;
function syncArtwork() {
  artworkEnabled.value = Boolean(artworkMedia?.matches) &&
    document.documentElement.dataset.reducedMotion !== 'reduce';
}
onMounted(() => {
  artworkMedia = window.matchMedia('(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)');
  syncArtwork();
  artworkMedia.addEventListener('change', syncArtwork);
  artworkPreference = new MutationObserver(syncArtwork);
  artworkPreference.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-reduced-motion'],
  });
});
onBeforeUnmount(() => {
  artworkMedia?.removeEventListener('change', syncArtwork);
  artworkPreference?.disconnect();
});
useMarketPointerReveal((state) => {
  const element = lens.value;
  if (!element) return;
  element.style.opacity = state.active && !state.local ? '1' : '0';
  element.dataset.surface = state.surface;
  if (!state.active || state.local) return;
  element.style.transform = `translate3d(${state.x - 112}px, ${state.y - 112}px, 0)`;
  element.style.setProperty('--market-pointer-radius', `${state.radius}px`);
  overprint.value?.setLensPosition(state.x - 112, state.y - 112);
});
</script>
<template>
  <div ref="lens" class="market-pointer-reveal" aria-hidden="true">
    <SurveyOverprint v-if="artworkEnabled" ref="overprint" />
    <div class="market-pointer-reveal__ring" />
  </div>
</template>
<style scoped>
/* Same lens, ring and illustrations; its paint surface fits the largest circle. */
.market-pointer-reveal {
  position: fixed;
  top: 0;
  left: 0;
  width: 224px;
  height: 224px;
  z-index: 100;
  opacity: 0;
  pointer-events: none;
  overflow: hidden;
  contain: strict;
}
.market-pointer-reveal__ring {
  position: absolute;
  top: 0;
  left: 0;
  width: calc(var(--market-pointer-radius, 110px) * 2);
  height: calc(var(--market-pointer-radius, 110px) * 2);
  transform: translate3d(calc(112px - var(--market-pointer-radius, 110px)), calc(112px - var(--market-pointer-radius, 110px)), 0);
  border: 1px solid var(--color-brand-halo-strong);
  border-radius: 50%;
  background: radial-gradient(circle, transparent 72%, var(--color-brand-halo-soft));
  pointer-events: none;
}
@media (prefers-reduced-motion: reduce), (hover: none), (pointer: coarse) {
  .market-pointer-reveal { display: none; }
}
</style>
