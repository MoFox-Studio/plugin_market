<script setup lang="ts">
import { defineAsyncComponent } from 'vue';

const FoxPointCloud = defineAsyncComponent(() => import('./FoxPointCloud.vue'));
</script>

<template>
  <figure class="home-plate">
    <div class="plate-picture"><FoxPointCloud /></div>
    <figcaption>
      <span class="plate-index">图版一</span><i lang="en">MoFox in Blue</i>
      <span class="plate-index">社区图录</span>
    </figcaption>
  </figure>
</template>

<style scoped>
.home-plate {
  min-width: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}
.plate-picture {
  width: 100%;
  min-height: 240px;
  height: clamp(245px, 23vw, 330px);
  position: relative;
  pointer-events: none;
}
figcaption {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 3px;
}
.plate-index {
  font: 11px/1.4 var(--font-sans);
  letter-spacing: 0.06em;
  color: var(--ink-500);
}
figcaption i {
  font: 400 clamp(22px, 2.6vw, 35px) / 1 var(--font-script);
  color: var(--blue-700);
}
@media (max-width: 700px) {
  .plate-picture {
    min-height: 0;
    height: clamp(64px, 24vw, 112px);
  }
  .plate-picture :deep(.original-logo-frame) {
    width: 94%;
    padding: 4px;
  }
  .plate-picture :deep(.logo-register),
  .plate-picture :deep(.logo-scan),
  .plate-index,
  figcaption i {
    display: none;
  }
  figcaption {
    margin: 0;
  }
}
</style>
