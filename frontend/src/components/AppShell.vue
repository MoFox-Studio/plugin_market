<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AnnouncementBanner from '@/components/AnnouncementBanner.vue'
import AnnouncementModalQueue from '@/components/AnnouncementModalQueue.vue'
import AppFooter from '@/components/AppFooter.vue'
import AppHeader from '@/components/AppHeader.vue'
import AppSidebar from '@/components/AppSidebar.vue'

const route = useRoute()
const sidebarOpen = ref(false)

watch(() => route.fullPath, () => {
  sidebarOpen.value = false
})

/** 默认所有页面走 fluid layout：占满整个视口，不显示全局 sidebar
 * 全局 sidebar 设计在新方案里被各页面自己的 sidebar 取代，
 * 仅保留 fallback 给将来的次级页面（404 之类） */
const layoutMode = computed<'sidebar' | 'fluid'>(() => {
  if (route.name === 'notfound') return 'sidebar'
  return 'fluid'
})

const showFooter = computed(() => {
  // admin 自己有 layout，不需要全局 footer 占位
  return !String(route.name || '').startsWith('admin')
})
</script>

<template>
  <div class="app-shell" :data-layout="layoutMode">
    <AnnouncementModalQueue />
    <AnnouncementBanner />
    <AppHeader @toggle-sidebar="sidebarOpen = true" />

    <template v-if="layoutMode === 'sidebar'">
      <div class="app-shell-layout shell">
        <AppSidebar class="app-shell-nav" :open="sidebarOpen" @close="sidebarOpen = false" />
        <main class="app-shell-main">
          <div class="app-shell-content">
            <slot />
          </div>
        </main>
      </div>
    </template>

    <template v-else>
      <main class="app-shell-fluid">
        <slot />
      </main>
    </template>

    <AppFooter v-if="showFooter" />
  </div>
</template>

<style scoped>
.app-shell-fluid { min-width: 0; flex: 1; }
.app-shell[data-layout="fluid"] { display: flex; flex-direction: column; }
</style>
