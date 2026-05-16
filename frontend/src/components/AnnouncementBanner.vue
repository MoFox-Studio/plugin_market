<script setup lang="ts">
import { computed } from 'vue'
import { useAnnouncementsStore } from '@/stores/announcements'

const announcements = useAnnouncementsStore()

const banner = computed(() => announcements.activeBanners[0] || null)

const severityLabel = computed(() => {
  if (!banner.value) {
    return ''
  }
  if (banner.value.severity === 'critical') {
    return 'Critical'
  }
  if (banner.value.severity === 'warning') {
    return 'Warning'
  }
  return 'Notice'
})

async function dismissBanner(): Promise<void> {
  if (!banner.value) {
    return
  }
  await announcements.dismiss(banner.value.id).catch(() => {})
}
</script>

<template>
  <transition name="announcement-banner">
    <section
      v-if="banner"
      class="announcement-banner"
      :class="`is-${banner.severity}`"
      role="status"
      aria-live="polite"
    >
      <div class="announcement-banner-inner shell">
        <div class="announcement-banner-copy">
          <span class="announcement-banner-kicker">{{ severityLabel }}</span>
          <strong>{{ banner.title }}</strong>
          <p>{{ banner.body_markdown }}</p>
        </div>
        <button
          v-if="banner.dismissible"
          type="button"
          class="announcement-banner-close"
          aria-label="关闭公告"
          @click="dismissBanner"
        >
          <span aria-hidden="true">×</span>
        </button>
      </div>
    </section>
  </transition>
</template>