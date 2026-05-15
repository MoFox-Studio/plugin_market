<script setup lang="ts">
defineProps({
  level: { type: String, default: 'community' },
})

const labels: Record<string, string> = { official: '官方', verified: '认证', community: '社区' }
</script>

<template>
  <span :class="['badge', `trust-${level}`]">{{ labels[level] || level }}</span>
</template>
