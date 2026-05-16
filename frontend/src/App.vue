<script setup lang="ts">
import { onBeforeUnmount, onMounted, watch } from 'vue'
import { useAnnouncementsStore } from '@/stores/announcements'
import { useAuthStore } from '@/stores/auth'
import { useInboxStore } from '@/stores/inbox'
import AppShell from '@/components/AppShell.vue'
import AppToast from '@/components/AppToast.vue'
import DisclaimerModal from '@/components/DisclaimerModal.vue'

const announcements = useAnnouncementsStore()
const auth = useAuthStore()
const inbox = useInboxStore()

let motionMedia: MediaQueryList | null = null

function syncReducedMotion() {
  if (typeof document === 'undefined') {
    return
  }
  const root = document.documentElement
  root.dataset.reducedMotion = motionMedia?.matches ? 'reduce' : 'no-preference'
}

function handleReducedMotionChange() {
  syncReducedMotion()
}

watch(
  () => auth.viewer?.author_id,
  (authorId) => {
    void announcements.loadActive(true)

    if (authorId) {
      inbox.startPolling()
      return
    }
    inbox.stopPolling({ clearState: true })
  },
)

onMounted(() => {
  auth.loadViewer()
  void announcements.loadActive()

  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    syncReducedMotion()
    return
  }

  motionMedia = window.matchMedia('(prefers-reduced-motion: reduce)')
  syncReducedMotion()

  if (typeof motionMedia.addEventListener === 'function') {
    motionMedia.addEventListener('change', handleReducedMotionChange)
    return
  }

  motionMedia.addListener(handleReducedMotionChange)
})

onBeforeUnmount(() => {
  inbox.stopPolling()

  if (motionMedia === null) {
    return
  }

  if (typeof motionMedia.removeEventListener === 'function') {
    motionMedia.removeEventListener('change', handleReducedMotionChange)
    return
  }

  motionMedia.removeListener(handleReducedMotionChange)
})
</script>

<template>
  <AppToast />
  <DisclaimerModal />
  <AppShell>
    <router-view />
  </AppShell>
</template>
