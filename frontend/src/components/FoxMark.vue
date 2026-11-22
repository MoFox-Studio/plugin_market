<script setup lang="ts">
withDefaults(defineProps<{ size?: number; alt?: string }>(), {
  size: 32,
  alt: '',
});
</script>
<template>
  <img
    class="mofox-original-logo"
    :src="'/logo.png'"
    :width="size"
    :height="size"
    :alt="alt"
    decoding="async"
    draggable="false"
  />
</template>
<style scoped>
.mofox-original-logo {
  display: block;
  flex-shrink: 0;
  max-width: 100%;
  object-fit: contain;
}
</style>
