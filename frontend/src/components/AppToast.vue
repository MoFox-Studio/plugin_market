<script setup lang="ts">
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()
</script>

<template>
  <div
    class="toast"
    :class="toast.kind"
    :hidden="!toast.visible"
  >{{ toast.message }}</div>
</template>
