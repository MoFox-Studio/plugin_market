<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps<{
  count?: number
  /** 显示当前页面标签，比如 "BROWSE" / "VOL.18" 等 */
  pageLabel?: string
}>()

const router = useRouter()

const today = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
})

const volNumber = computed(() => {
  const epoch = new Date('2026-01-01').getTime()
  const now = new Date().getTime()
  const week = Math.floor((now - epoch) / (7 * 24 * 3600 * 1000)) + 1
  return Math.max(1, week)
})

function goBrowse(): void {
  void router.push({ name: 'market' })
}
</script>

<template>
  <div class="vol-kicker">
    <div>
      <span class="vol-num">{{ pageLabel || `VOL.${volNumber}` }}</span>
      <span v-if="!pageLabel">五月号 · 周刊</span>
      <template v-if="count != null">
        <span> · 本期 {{ count }} 条更新</span>
      </template>
    </div>
    <div class="right">
      <span>{{ today }}</span>
      <a href="#" @click.prevent="goBrowse">查看全部 →</a>
    </div>
  </div>
</template>
