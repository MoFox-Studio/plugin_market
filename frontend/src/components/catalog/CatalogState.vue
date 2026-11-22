<script setup lang="ts">
withDefaults(
  defineProps<{
    loading?: boolean;
    error?: string;
    empty?: boolean;
    title?: string;
    message?: string;
    cards?: boolean;
    count?: number;
  }>(),
  { count: 6, title: '这里还没有内容', message: '稍后再来看看。' },
);
defineEmits<{ retry: [] }>();
</script>
<template>
  <div
    v-if="loading"
    class="catalog-state-loading"
    :class="{ 'is-cards': cards }"
    role="status"
    aria-busy="true"
  >
    <span class="catalog-state-sr">正在加载内容</span>
    <div
      v-for="n in count"
      :key="n"
      class="catalog-state-placeholder"
      aria-hidden="true"
    >
      <i></i><i></i><i></i>
    </div>
  </div>
  <div v-else-if="error" class="catalog-state" role="alert">
    <span class="state-mark" aria-hidden="true">!</span>
    <h2>暂时无法加载</h2>
    <p>{{ error }}</p>
    <button type="button" class="btn" @click="$emit('retry')">
      重新加载 ↻
    </button>
  </div>
  <div v-else-if="empty" class="catalog-state">
    <span class="state-mark" aria-hidden="true">∅</span>
    <h2>{{ title }}</h2>
    <p>{{ message }}</p>
    <slot name="empty-action" />
  </div>
  <slot v-else />
</template>
<style scoped>
.catalog-state {
  display: grid;
  justify-items: center;
  align-content: center;
  gap: 12px;
  padding: 44px 20px;
  min-height: 200px;
  border: 1px dashed var(--line);
  background: var(--surface);
  text-align: center;
}
.state-mark {
  font: 26px var(--font-mono);
  color: var(--blue-600);
}
.catalog-state h2 {
  margin: 0;
  font: 600 17px var(--font-sans);
}
.catalog-state p {
  margin: 0 0 6px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ink-500);
  overflow-wrap: anywhere;
}
.catalog-state-loading {
  display: grid;
  gap: 16px;
}
.catalog-state-loading.is-cards {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.catalog-state-placeholder {
  padding: 24px;
  border: 1px solid var(--line);
  min-height: 120px;
  display: grid;
  align-content: start;
  gap: 14px;
  background: var(--surface);
}
.is-cards .catalog-state-placeholder {
  min-height: 250px;
}
.catalog-state-placeholder i {
  display: block;
  height: 12px;
  background: var(--surface-hover);
  width: 85%;
  animation: catalog-pulse 1.6s ease-in-out infinite;
}
.catalog-state-placeholder i:first-child {
  width: 46px;
  height: 40px;
}
.catalog-state-placeholder i:last-child {
  width: 60%;
}
.catalog-state-sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
@keyframes catalog-pulse {
  50% {
    opacity: 0.45;
  }
}
@media (max-width: 1100px) {
  .catalog-state-loading.is-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 620px) {
  .catalog-state-loading.is-cards {
    grid-template-columns: 1fr;
  }
}
@media (prefers-reduced-motion: reduce) {
  .catalog-state-placeholder i {
    animation: none;
  }
}
:global(:root[data-reduced-motion='reduce'] .catalog-state-placeholder i) {
  animation: none;
}
</style>
