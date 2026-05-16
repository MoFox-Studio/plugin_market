<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'

withDefaults(defineProps<{
  to: RouteLocationRaw
  label: string
  meta?: string
  compact?: boolean
}>(), {
  meta: '',
  compact: false,
})

defineEmits<{
  (e: 'navigate'): void
}>()
</script>

<template>
  <RouterLink
    :to="to"
    class="app-sidebar-link"
    :class="{ 'is-compact': compact }"
    active-class="is-active"
    exact-active-class="is-active"
    @click="$emit('navigate')"
  >
    <span class="app-sidebar-link-label">{{ label }}</span>
    <small v-if="meta" class="app-sidebar-link-meta">{{ meta }}</small>
  </RouterLink>
</template>