<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue';
import { routeBusy, routeError } from '@/composables/useLoadingState';
const visible = ref(false);
const slow = ref(false);
function reload() {
  window.location.reload();
}
let delay: ReturnType<typeof setTimeout>;
let slowTimer: ReturnType<typeof setTimeout>;
watch(
  routeBusy,
  (busy) => {
    clearTimeout(delay);
    clearTimeout(slowTimer);
    visible.value = false;
    slow.value = false;
    if (busy) {
      delay = setTimeout(() => (visible.value = true), 150);
      slowTimer = setTimeout(() => (slow.value = true), 3000);
    }
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  clearTimeout(delay);
  clearTimeout(slowTimer);
});
</script>
<template>
  <div
    v-if="visible"
    class="route-progress"
    role="progressbar"
    aria-label="正在加载页面"
  >
    <span />
  </div>
  <p v-if="slow" class="route-slow" role="status">加载时间比平时长…</p>
  <div v-if="routeError" class="route-failed" role="alert">
    <span>{{ routeError }}</span
    ><button class="btn btn-sm" @click="reload">刷新页面</button>
  </div>
</template>
<style scoped>
.route-progress {
  position: fixed;
  top: 0;
  left: 72px;
  right: 0;
  height: 3px;
  overflow: hidden;
  background: var(--blue-100);
  z-index: 200;
}
.route-progress span {
  display: block;
  width: 35%;
  height: 100%;
  background: var(--blue-500);
  animation: route-sweep 1.3s ease-in-out infinite;
}
.route-slow {
  position: fixed;
  right: 24px;
  top: 64px;
  background: var(--surface);
  border: 1px solid var(--line);
  padding: 8px 14px;
  z-index: 80;
  font-size: 12px;
}
.route-failed {
  position: fixed;
  top: 64px;
  left: 72px;
  right: 0;
  display: flex;
  justify-content: center;
  gap: 16px;
  padding: 16px;
  background: var(--surface);
  border-bottom: 1px solid var(--danger);
  z-index: 80;
}
@keyframes route-sweep {
  from {
    transform: translateX(-100%);
  }
  to {
    transform: translateX(390%);
  }
}
@media (max-width: 760px) {
  .route-progress,
  .route-failed {
    left: 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .route-progress span {
    animation: none;
    width: 100%;
    opacity: 0.65;
  }
}
</style>
