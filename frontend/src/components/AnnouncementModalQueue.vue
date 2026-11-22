<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import { useAnnouncementsStore } from '@/stores/announcements';
import type { Announcement } from '@/types';
import AnnouncementModal from '@/components/AnnouncementModal.vue';

const announcements = useAnnouncementsStore();
const consumedInSession = ref<number[]>([]);
const currentId = ref<number | null>(null);
const blocked = ref(false);
let overlayObserver: MutationObserver | null = null;
function syncOverlay() {
  blocked.value = Array.from(
    document.querySelectorAll('dialog[open], [aria-modal="true"]'),
  ).some(
    (element) =>
      !element.closest('[data-announcement-queue]') &&
      element.getAttribute('aria-hidden') !== 'true',
  );
}
onMounted(() => {
  syncOverlay();
  overlayObserver = new MutationObserver(syncOverlay);
  overlayObserver.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['open', 'aria-modal', 'aria-hidden'],
  });
});
onBeforeUnmount(() => overlayObserver?.disconnect());

const queue = computed(() =>
  announcements.activeModals.filter(
    (item) => !consumedInSession.value.includes(item.id),
  ),
);
const current = computed(() => {
  if (currentId.value !== null) {
    return queue.value.find((item) => item.id === currentId.value) || null;
  }
  return queue.value[0] || null;
});

watch(
  queue,
  (items) => {
    if (!items.length) {
      currentId.value = null;
      return;
    }
    if (
      currentId.value === null ||
      !items.some((item) => item.id === currentId.value)
    ) {
      currentId.value = items[0].id;
    }
  },
  { immediate: true },
);

function consume(announcement: Announcement): void {
  if (!consumedInSession.value.includes(announcement.id)) {
    consumedInSession.value = [...consumedInSession.value, announcement.id];
  }
  const next = queue.value.find((item) => item.id !== announcement.id);
  currentId.value = next?.id || null;
}

async function dismissAnnouncement(announcement: Announcement): Promise<void> {
  await announcements.dismiss(announcement.id).catch(() => {});
  consume(announcement);
}

function closeAnnouncement(announcement: Announcement): void {
  consume(announcement);
}
</script>

<template>
  <div data-announcement-queue>
    <AnnouncementModal
      v-if="current && !blocked"
      :announcement="current"
      @dismiss="dismissAnnouncement"
      @close="closeAnnouncement"
    />
  </div>
</template>
