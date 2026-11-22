<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import AnnouncementBanner from './AnnouncementBanner.vue';
import AppFooter from './AppFooter.vue';
import AppHeader from './AppHeader.vue';
import AppSidebar from './AppSidebar.vue';
import ContourField from './ContourField.vue';
import GlobalPointerReveal from './GlobalPointerReveal.vue';
const route = useRoute();
const sidebarOpen = ref(false);
watch(
  () => route.fullPath,
  () => (sidebarOpen.value = false),
);
const showFooter = computed(
  () => !String(route.name || '').startsWith('admin'),
);
</script>
<template>
  <div class="market-shell">
    <ContourField />
    <GlobalPointerReveal />
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <AppSidebar :open="sidebarOpen" @close="sidebarOpen = false" />
    <div class="market-stage">
      <AppHeader @toggle-sidebar="sidebarOpen = true" /><AnnouncementBanner />
      <main id="main-content" tabindex="-1"><slot /></main>
      <AppFooter v-if="showFooter" />
    </div>
  </div>
</template>
