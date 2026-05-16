<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAnnouncementsStore } from '@/stores/announcements'
import { useInboxStore } from '@/stores/inbox'
import type { Announcement } from '@/types'
import EmptyState from '@/components/EmptyState.vue'
import InboxList from '@/components/InboxList.vue'
import AnnouncementModal from '@/components/AnnouncementModal.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const announcements = useAnnouncementsStore()
const inbox = useInboxStore()

const announcementId = computed(() => {
  const raw = route.query.announcement
  const value = Array.isArray(raw) ? raw[0] : raw
  return value ? Number(value) : null
})

const modalAnnouncement = computed<Announcement | null>(() => {
  if (!announcementId.value) {
    return null
  }
  const active = announcements.items.find((item) => item.id === announcementId.value)
  if (active) {
    return active
  }
  const message = inbox.messages.find((item) => item.related_announcement_id === announcementId.value || item.link?.announcement_id === announcementId.value)
  if (!message) {
    return null
  }
  return {
    id: announcementId.value,
    title: String(message.payload.title || '公告详情'),
    body_markdown: String(message.payload.preview || message.preview || '该公告当前无法获取完整正文。'),
    display_mode: (message.payload.display_mode as Announcement['display_mode']) || 'modal',
    severity: (message.payload.severity as Announcement['severity']) || 'info',
    dismissible: true,
    enabled: true,
    starts_at: null,
    ends_at: null,
    audience: 'logged_in',
    emit_inbox: true,
    dismiss_token: 0,
    created_by: 'system',
    created_at: message.created_at,
    updated_at: message.created_at,
  }
})

async function closeModal(): Promise<void> {
  const nextQuery = { ...route.query }
  delete nextQuery.announcement
  await router.replace({ name: 'inbox', query: nextQuery })
}

async function dismissModal(announcement: Announcement): Promise<void> {
  const active = announcements.items.find((item) => item.id === announcement.id)
  if (active?.dismissible) {
    await announcements.dismiss(announcement.id).catch(() => {})
  }
  await closeModal()
}

onMounted(() => {
  void announcements.loadActive()
  void inbox.loadUnreadCount()
})
</script>

<template>
  <div v-if="!auth.isAuthenticated" style="padding-top:40px">
    <EmptyState title="请先登录" message="登录后才能查看完整信箱消息。" />
    <div style="text-align:center;margin-top:12px">
      <a class="btn btn-primary" :href="auth.getLoginUrl('/inbox')">GitHub 登录</a>
    </div>
  </div>

  <div v-else class="control-room">
    <section class="control-hero creator-hero">
      <div class="control-hero-copy">
        <span class="control-kicker">Inbox</span>
        <h1>全屏收件箱</h1>
        <p>集中处理提及、回复、治理通知和公告消息，保留类型过滤、分页和全部已读操作。</p>
      </div>
      <div class="profile-card">
        <strong>未读消息</strong>
        <span>{{ inbox.unreadCount }} 条</span>
        <div class="table-actions">
          <button class="btn btn-sm" type="button" :disabled="!inbox.hasUnread" @click="inbox.markAllRead()">全部已读</button>
        </div>
      </div>
    </section>

    <section class="panel">
      <InboxList eager />
    </section>

    <AnnouncementModal
      v-if="modalAnnouncement"
      :announcement="modalAnnouncement"
      @close="closeModal"
      @dismiss="dismissModal"
    />
  </div>
</template>