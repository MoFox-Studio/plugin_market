<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue';
import PageSkeleton from './PageSkeleton.vue';
const props = withDefaults(
  defineProps<{
    loading?: boolean;
    error?: string | null;
    empty?: boolean;
    label?: string;
  }>(),
  { label: '内容' },
);
defineEmits<{ retry: [] }>();
const slow = ref(false);
let timer: ReturnType<typeof setTimeout>;
watch(
  () => props.loading,
  (value) => {
    clearTimeout(timer);
    slow.value = false;
    if (value) timer = setTimeout(() => (slow.value = true), 3000);
  },
  { immediate: true },
);
onBeforeUnmount(() => clearTimeout(timer));
</script>
<template>
  <div :aria-busy="loading || undefined" class="async-section">
    <template v-if="loading"
      ><slot name="loading"><PageSkeleton /></slot>
      <p v-if="slow" class="async-note" role="status">
        加载时间比平时长，请稍候…
      </p></template
    >
    <div v-else-if="error" class="async-message" role="status">
      <span class="eyebrow">REQUEST FAILED</span>
      <h3>{{ label }}加载失败</h3>
      <p>{{ error }}</p>
      <button class="btn" @click="$emit('retry')">重新加载 ↗</button>
    </div>
    <div v-else-if="empty" class="async-message">
      <span class="eyebrow">NO RESULTS</span>
      <h3>暂时没有{{ label }}</h3>
      <slot name="empty" />
    </div>
    <slot v-else />
  </div>
</template>
<style scoped>
.async-message {
  border: 1px solid var(--line);
  padding: 40px 24px;
  background: var(--surface);
  text-align: center;
}
.async-message h3 {
  margin: 12px 0;
  font-size: 20px;
}
.async-message p,
.async-note {
  color: var(--ink-500);
}
.async-note {
  text-align: center;
}
</style>
