<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useAnnouncementsStore } from '@/stores/announcements';
import { useInboxStore } from '@/stores/inbox';
import type { Announcement } from '@/types';
import PageSkeleton from '@/components/PageSkeleton.vue';
import InboxList from '@/components/InboxList.vue';
import AnnouncementModal from '@/components/AnnouncementModal.vue';

const authChecking = ref(true);
const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const announcements = useAnnouncementsStore();
const inbox = useInboxStore();

const announcementId = computed(() => {
  const raw = route.query.announcement;
  const value = Array.isArray(raw) ? raw[0] : raw;
  return value ? Number(value) : null;
});

const modalAnnouncement = computed<Announcement | null>(() => {
  if (!announcementId.value) {
    return null;
  }
  const active = announcements.items.find(
    (item) => item.id === announcementId.value,
  );
  if (active) {
    return active;
  }
  const message = inbox.messages.find(
    (item) =>
      item.related_announcement_id === announcementId.value ||
      item.link?.announcement_id === announcementId.value,
  );
  if (!message) {
    return null;
  }
  return {
    id: announcementId.value,
    title: String(message.payload.title || '公告详情'),
    body_markdown: String(
      message.payload.preview ||
        message.preview ||
        '该公告当前无法获取完整正文。',
    ),
    display_mode:
      (message.payload.display_mode as Announcement['display_mode']) || 'modal',
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
  };
});

async function closeModal(): Promise<void> {
  const nextQuery = { ...route.query };
  delete nextQuery.announcement;
  await router.replace({ path: route.path, query: nextQuery });
}

async function dismissModal(announcement: Announcement): Promise<void> {
  const active = announcements.items.find(
    (item) => item.id === announcement.id,
  );
  if (active?.dismissible) {
    await announcements.dismiss(announcement.id).catch(() => {});
  }
  await closeModal();
}

onMounted(async () => {
  await auth.loadViewer();
  authChecking.value = false;
  void announcements.loadActive();
  if (auth.isAuthenticated) void inbox.loadUnreadCount();
});
</script>

<template>
  <div class="page-wrap inbox-page">
    <header class="inbox-heading">
      <div class="mail-running"><b>社区通讯</b><span>来信与通知</span></div>
      <div>
        <h1>社区信箱</h1>
        <p v-if="auth.viewer">收件人 · {{ auth.viewer.display_name }}</p>
        <p v-else>查收社区的回复、作者动态和市场通知。</p>
      </div>
      <div v-if="auth.isAuthenticated" class="unread-counter">
        <strong>{{ inbox.loadingUnread && !inbox.lastLoadedAt ? '—' : inbox.unreadCount }}</strong
        ><span>未读消息</span>
      </div>
    </header>
    <PageSkeleton v-if="authChecking || auth.loading" type="rows" :count="4" />
    <section v-else-if="auth.error" class="inbox-error" role="alert">
      <h2>暂时无法确认登录状态</h2>
      <p>{{ auth.error }}</p>
      <button class="btn" @click="auth.loadViewer(true)">重新连接</button>
    </section>
    <div v-else class="mail-columns">
      <aside class="mail-index" aria-label="来信类别说明">
        <h2>来信分类</h2>
        <dl><div><dt>互动</dt><dd>提及你的留言与回复</dd></div>
          <div><dt>动态</dt><dd>作者与插件的更新</dd></div>
          <div><dt>通知</dt><dd>公告、治理与系统消息</dd></div></dl>
      </aside>
      <section v-if="!auth.isAuthenticated" class="inbox-access">
        <div class="mail-envelope" aria-hidden="true">
          <svg viewBox="0 0 76 42" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M1 1h54v36H1zM2 2l26 21L54 2M2 36l17-17m34 17L37 20M61 8h14m-14 6h10m-10 6h7"/></svg>
        </div>
        <h2>登录后查收来信</h2>
        <p>信件按 GitHub 账号投递。打开消息即可查看对应的讨论、作品或公告。</p>
        <a class="btn btn-primary" :href="auth.getLoginUrl('/inbox')">使用 GitHub 登录 ↗</a>
      </section>
      <section v-else class="inbox-panel" aria-label="收件列表">
        <InboxList :key="auth.viewer?.author_id" eager />
      </section>
    </div>
    <AnnouncementModal
      v-if="modalAnnouncement && auth.isAuthenticated"
      :announcement="modalAnnouncement"
      @close="closeModal"
      @dismiss="dismissModal"
    />
  </div>
</template>
<style scoped>
.inbox-page {
  display: grid;
  gap: 28px;
}
.inbox-heading {
  display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 19px 24px;
  align-items: end; padding-bottom: 22px; border-bottom: 3px double var(--ink-700);
}
.mail-running {
  grid-column: 1/-1; display: flex; justify-content: space-between; align-items: center;
  font-size: 11px; letter-spacing: .14em; border-top: 2px solid var(--ink-900);
  padding: 8px 0; border-bottom: 1px solid var(--line-strong);
}
.mail-running b { color: var(--blue-700); }
.inbox-heading h1 { margin: 0 0 11px; font: 800 clamp(44px, 6vw, 80px)/1.13 var(--font-editorial); letter-spacing: -.05em; }
.inbox-heading p { margin: 0; line-height: 1.75; color: var(--ink-700); }
.unread-counter { border-left: 1px solid var(--line-strong); display: grid; gap: 2px; padding: 0 0 0 24px; }
.unread-counter strong { font: 800 clamp(28px, 3.4vw, 48px)/1.2 var(--font-editorial); color: var(--blue-700); }
.unread-counter span { font-size: 11px; color: var(--ink-500); }
.mail-columns { display: grid; grid-template-columns: minmax(155px, 1fr) minmax(0, 3.2fr); gap: clamp(18px, 3.5vw, 50px); align-items: start; }
.mail-index { border-top: 1px solid var(--ink-700); border-bottom: 1px solid var(--line); padding: 13px 0; }
.mail-index h2 { margin: 0 0 12px; font: 800 19px/1.3 var(--font-editorial); }
.mail-index dl { margin: 0; }
.mail-index dl div { padding: 10px 0; border-top: 1px solid var(--line); }
.mail-index dt { color: var(--blue-700); font-size: 13px; font-weight: 650; }
.mail-index dd { margin: 5px 0 0; font-size: 12px; color: var(--ink-500); line-height: 1.55; }
.inbox-access, .inbox-panel { min-width: 0; border-top: 2px solid var(--ink-700); border-bottom: 1px solid var(--line-strong); background: var(--surface); }
.inbox-access { padding: clamp(24px, 4vw, 52px); display: grid; justify-items: start; }
.mail-envelope { color: var(--blue-700); margin-bottom: 20px; }
.mail-envelope svg { display: block; width: 75px; height: 42px; }
.inbox-access h2 { margin: 0; font: 800 clamp(26px, 3vw, 40px)/1.35 var(--font-editorial); }
.inbox-access p { margin: 14px 0 22px; max-width: 37em; color: var(--ink-700); line-height: 1.8; }
.inbox-error { padding: 22px; border-left: 3px solid var(--danger); background: var(--danger-soft); color: var(--danger-ink); }
.inbox-error h2 { margin: 0; font: 800 22px/1.35 var(--font-editorial); }
@media (max-width: 700px) {
  .mail-columns { grid-template-columns: 1fr; }
  .mail-index { order: 2; }
  .mail-index dl { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
  .unread-counter { padding-left: 14px; }
}
</style>
