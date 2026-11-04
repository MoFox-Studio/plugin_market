<script setup lang="ts">
import { ref } from 'vue';
import { useMarketPointerReveal } from '@/composables/useMarketPointerReveal';
import SurveyOverprint from './SurveyOverprint.vue';

const lens = ref<HTMLElement | null>(null);
useMarketPointerReveal((state) => {
  if (lens.value) {
    lens.value.style.opacity = state.active && !state.local ? '1' : '0';
    lens.value.dataset.surface = state.surface;
  }
});
</script>
<template>
  <div ref="lens" class="market-pointer-reveal" aria-hidden="true">
    <SurveyOverprint />
    <div class="market-pointer-reveal__ring" />
  </div>
</template>
<style scoped>
.market-pointer-reveal {
  position: fixed;
  inset: 0;
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
  transform: translate3d(
    calc(var(--market-pointer-x, 0px) - var(--market-pointer-radius, 110px)),
    calc(var(--market-pointer-y, 0px) - var(--market-pointer-radius, 110px)),
    0
  );
  border: 1px solid var(--color-brand-halo-strong);
  border-radius: 50%;
  background: radial-gradient(
    circle,
    transparent 72%,
    var(--color-brand-halo-soft)
  );
  pointer-events: none;
}
@media (prefers-reduced-motion: reduce), (hover: none), (pointer: coarse) {
  .market-pointer-reveal {
    display: none;
  }
}
</style>
