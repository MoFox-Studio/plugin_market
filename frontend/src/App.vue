<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useAnnouncementsStore } from '@/stores/announcements';
import { useAuthStore } from '@/stores/auth';
import { useInboxStore } from '@/stores/inbox';
import AppShell from '@/components/AppShell.vue';
import AppToast from '@/components/AppToast.vue';
import MarketDialogHost from '@/components/MarketDialogHost.vue';
import DisclaimerModal from '@/components/DisclaimerModal.vue';
import AnnouncementModalQueue from '@/components/AnnouncementModalQueue.vue';
import RouteLoadingBar from '@/components/RouteLoadingBar.vue';
import { booting, routeError } from '@/composables/useLoadingState';
import PageSkeleton from '@/components/PageSkeleton.vue';
import { useHomeStore } from '@/stores/home';
import { useSubscriptionStore } from '@/stores/subscriptions';

const announcements = useAnnouncementsStore();
const auth = useAuthStore();
const inbox = useInboxStore();
const disclaimerResolved = ref(false);
const home = useHomeStore();

let motionMedia: MediaQueryList | null = null;
let announcementsRefreshTimer: number | null = null;
let announcementsGeneration = 0;

function syncReducedMotion() {
  if (typeof document === 'undefined') {
    return;
  }
  const root = document.documentElement;
  root.dataset.reducedMotion = motionMedia?.matches
    ? 'reduce'
    : 'no-preference';
}

function handleReducedMotionChange() {
  syncReducedMotion();
}

function stopAnnouncementsPolling() {
  ++announcementsGeneration;
  if (announcementsRefreshTimer !== null) {
    window.clearTimeout(announcementsRefreshTimer);
    announcementsRefreshTimer = null;
  }
}

async function refreshAnnouncements(force = false) {
  const generation = announcementsGeneration;
  await announcements.loadActive(force);
  if (generation === announcementsGeneration) {
    announcementsRefreshTimer = window.setTimeout(() => {
      announcementsRefreshTimer = null;
      void refreshAnnouncements(true);
    }, 30000);
  }
}

watch(
  () => auth.viewer?.author_id,
  (authorId) => {
    inbox.stopPolling({ clearState: true });
    useSubscriptionStore().$reset();
    home.invalidate({ clearData: true });
    stopAnnouncementsPolling();
    announcements.reset();
    void refreshAnnouncements(true);

    if (authorId) {
      inbox.startPolling();
      return;
    }
    inbox.stopPolling({ clearState: true });
  },
);

onMounted(() => {
  auth.loadViewer();
  void refreshAnnouncements();

  if (
    typeof window === 'undefined' ||
    typeof window.matchMedia !== 'function'
  ) {
    syncReducedMotion();
    return;
  }

  motionMedia = window.matchMedia('(prefers-reduced-motion: reduce)');
  syncReducedMotion();

  if (typeof motionMedia.addEventListener === 'function') {
    motionMedia.addEventListener('change', handleReducedMotionChange);
    return;
  }

  motionMedia.addListener(handleReducedMotionChange);
});

onBeforeUnmount(() => {
  inbox.stopPolling();
  stopAnnouncementsPolling();

  if (motionMedia === null) {
    return;
  }

  if (typeof motionMedia.removeEventListener === 'function') {
    motionMedia.removeEventListener('change', handleReducedMotionChange);
    return;
  }

  motionMedia.removeListener(handleReducedMotionChange);
});
</script>

<template>
  <AppToast />
  <MarketDialogHost />
  <RouteLoadingBar />
  <DisclaimerModal v-if="!booting" @resolved="disclaimerResolved = true" />
  <AnnouncementModalQueue v-if="!booting && disclaimerResolved" />
  <AppShell>
    <router-view v-slot="{ Component }">
      <component :is="Component" v-if="Component" />
      <PageSkeleton
        v-else-if="!routeError"
        type="detail"
        :count="2"
        style="margin: 32px"
      />
      <div v-else style="min-height: 50vh" aria-label="页面启动失败" />
    </router-view>
  </AppShell>
</template>
