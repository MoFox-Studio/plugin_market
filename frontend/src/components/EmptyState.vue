<template>
  <div class="empty-state">
    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true">
      <circle cx="11" cy="11" r="8"/>
      <line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
    <strong>{{ title }}</strong>
    <p v-if="message">{{ message }}</p>
  </div>
</template>

<script setup lang="ts">
defineProps({
  title: { type: String, default: '暂无数据' },
  message: { type: String, default: '' },
})
</script>

<style scoped>
.empty-state {
  display: grid;
  place-items: center;
  gap: 6px;
  padding: var(--space-10) var(--space-5);
  text-align: center;
  background: var(--surface);
  border: 1.5px dashed var(--line);
  border-radius: var(--radius-md);
  color: var(--ink-500);
}
.empty-state svg {
  color: var(--ink-300);
  flex: 0 0 auto;
  margin-bottom: var(--space-2);
}
.empty-state strong {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 16px;
  color: var(--ink-700);
}
.empty-state p {
  margin: 0;
  font-size: 13px;
  color: var(--ink-500);
  max-width: 40ch;
  line-height: 1.55;
}
</style>
