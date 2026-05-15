<script setup lang="ts">
import { starPercent } from '@/utils/format'

defineProps({
  score: { type: Number, default: 0 },
})
</script>

<template>
  <span class="rating">
    <span class="stars" aria-hidden="true">
      ★★★★★
      <span class="fill" :style="{ width: starPercent(score) + '%' }">★★★★★</span>
    </span>
  </span>
</template>
