<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAnnouncementsStore } from '@/stores/announcements'
import type { Announcement } from '@/types'
import AnnouncementModal from '@/components/AnnouncementModal.vue'

const announcements = useAnnouncementsStore()
const consumedInSession = ref<number[]>([])
const currentId = ref<number | null>(null)

const queue = computed(() => announcements.activeModals.filter((item) => !consumedInSession.value.includes(item.id)))
const current = computed(() => {
  if (currentId.value !== null) {
    return queue.value.find((item) => item.id === currentId.value) || null
  }
  return queue.value[0] || null
})

watch(queue, (items) => {
  if (!items.length) {
    currentId.value = null
    return
  }
  if (currentId.value === null || !items.some((item) => item.id === currentId.value)) {
    currentId.value = items[0].id
  }
}, { immediate: true })

function consume(announcement: Announcement): void {
  if (!consumedInSession.value.includes(announcement.id)) {
    consumedInSession.value = [...consumedInSession.value, announcement.id]
  }
  const next = queue.value.find((item) => item.id !== announcement.id)
  currentId.value = next?.id || null
}

async function dismissAnnouncement(announcement: Announcement): Promise<void> {
  await announcements.dismiss(announcement.id).catch(() => {})
  consume(announcement)
}

function closeAnnouncement(announcement: Announcement): void {
  consume(announcement)
}
</script>

<template>
  <AnnouncementModal
    v-if="current"
    :announcement="current"
    @dismiss="dismissAnnouncement"
    @close="closeAnnouncement"
  />
</template>