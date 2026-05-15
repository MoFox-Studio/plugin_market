<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import AppFooter from '@/components/AppFooter.vue'
import AppToast from '@/components/AppToast.vue'
import DisclaimerModal from '@/components/DisclaimerModal.vue'

const auth = useAuthStore()

onMounted(() => {
  auth.loadViewer()
})
</script>

<template>
  <AppHeader />
  <AppToast />
  <DisclaimerModal />
  <main class="shell">
    <router-view />
  </main>
  <AppFooter />
</template>
