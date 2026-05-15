<template>
  <div class="empty">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <circle cx="11" cy="11" r="8"/>
      <line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
    <strong>{{ title }}</strong>
    <div>{{ message }}</div>
  </div>
</template>

<script setup lang="ts">
defineProps({
  title: { type: String, default: '暂无数据' },
  message: { type: String, default: '' },
})
</script>
