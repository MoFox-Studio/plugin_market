<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import PageSkeleton from '@/components/PageSkeleton.vue';

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

interface AdminGroup {
  title: string;
  items: Array<{
    name: string;
    label: string;
    upcoming?: boolean;
  }>;
}

const groups: AdminGroup[] = [
  {
    title: '值班',
    items: [
      { name: 'admin-dashboard', label: '仪表盘' },
      { name: 'admin-system', label: '系统状态' },
    ],
  },
  {
    title: '治理',
    items: [
      { name: 'admin-plugins', label: '插件治理' },
      { name: 'admin-versions', label: '版本治理', upcoming: true },
      { name: 'admin-authors', label: '作者管理' },
      { name: 'admin-comments', label: '评论审核' },
    ],
  },
  {
    title: '运营',
    items: [
      { name: 'admin-curation', label: '精选配置' },
      { name: 'admin-announcements', label: '公告管理' },
    ],
  },
  {
    title: '记录',
    items: [
      { name: 'admin-audit', label: '审计日志' },
      { name: 'admin-inbox', label: '后台信箱' },
    ],
  },
];

const currentRouteName = computed(() => String(route.name || ''));
const navigationOpen = ref(false);
watch(currentRouteName, () => {
  navigationOpen.value = false;
});
const currentTitle = computed(() => {
  for (const group of groups) {
    const hit = group.items.find((it) => it.name === currentRouteName.value);
    if (hit) return hit.label;
  }
  return '管理后台';
});

function backToSite() {
  void router.push({ name: 'home' });
}
</script>

<template>
  <div class="page-wrap admin-shell">
    <header class="admin-heading">
      <p class="desk-name"><span>MoFox</span> 市场编辑部</p>
      <button type="button" class="desk-return" @click="backToSite">返回市场 ↗</button>
    </header>
    <PageSkeleton v-if="auth.loading" type="rows" :count="3" />
    <section v-else-if="auth.error" class="permission-panel" role="status">
      <h1>身份确认失败</h1>
      <p>{{ auth.error }}</p>
      <button class="btn btn-primary" @click="auth.loadViewer(true)">
        重新确认身份
      </button>
    </section>
    <section v-else-if="!auth.isAuthenticated" class="permission-panel">
      <h1>登录后访问管理后台</h1>
      <p>此区域仅向管理员开放，登录后会返回当前页面。</p>
      <a class="btn btn-primary" :href="auth.getLoginUrl()"
        >使用 GitHub 登录 ↗</a
      >
    </section>
    <div v-else-if="auth.isAdmin" class="desk-workspace">
      <nav class="admin-navigation" aria-label="后台栏目">
        <button type="button" class="desk-menu-toggle" aria-controls="desk-sections"
          :aria-expanded="navigationOpen" @click="navigationOpen = !navigationOpen">
          <span>栏目目录</span>
          <strong>{{ currentTitle }}</strong>
          <span aria-hidden="true">{{ navigationOpen ? '−' : '+' }}</span>
        </button>
        <div id="desk-sections" class="desk-sections" :class="{ 'is-open': navigationOpen }">
          <p class="desk-index-title">工作栏目</p>
          <div v-for="group in groups" :key="group.title" class="admin-nav-group">
            <span class="nav-group-label">{{ group.title }}</span>
            <div>
              <RouterLink
                v-for="item in group.items"
                :key="item.name"
                :to="{ name: item.name }"
                :class="{ active: currentRouteName === item.name }"
                @click="navigationOpen = false"
                >{{ item.label
                }}<small v-if="item.upcoming">待开放</small></RouterLink
              >
            </div>
          </div>
        </div>
      </nav>
      <div class="admin-body">
        <router-view :key="auth.viewer?.author_id" />
      </div>
    </div>
    <section v-else class="permission-panel">
      <h1>需要管理员权限</h1>
      <p>当前身份无法访问市场控制中心。</p>
      <RouterLink class="btn btn-primary" to="/browse">返回插件目录</RouterLink>
    </section>
  </div>
</template>
<style scoped>
.admin-shell {
  display: grid;
  gap: clamp(20px, 3vw, 34px);
  width: 100%;
  max-width: 1480px;
  margin-inline: auto;
  padding: clamp(18px, 2.5vw, 38px) clamp(16px, 3vw, 50px) 48px;
  min-width: 0;
}
.admin-heading,
.desk-menu-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.admin-heading {
  border-block: 1px solid var(--ink-700);
  padding-block: 10px;
  border-bottom: 3px double var(--ink-700);
}
.desk-name {
  margin: 0;
  font: 650 17px/1.3 var(--font-editorial);
}
.desk-name span {
  margin-right: .35em;
  font-style: italic;
  color: var(--blue-700);
}
.desk-return {
  min-height: 32px;
  color: var(--ink-700);
  text-decoration: underline;
  text-underline-offset: 4px;
  font: 12px var(--font-sans);
}
.desk-workspace {
  display: grid;
  grid-template-columns: clamp(128px, 12vw, 174px) minmax(0, 1fr);
  align-items: start;
  gap: clamp(22px, 3vw, 44px);
}
.admin-navigation {
  position: sticky;
  top: 84px;
  max-height: calc(100dvh - 104px);
  overflow: auto;
  border-right: 1px solid var(--line-strong);
  padding-right: 14px;
}
.desk-menu-toggle { display: none; }
.desk-index-title {
  margin: 0 0 12px;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--ink-700);
  font: 650 19px var(--font-editorial);
}
.admin-nav-group {
  padding: 9px 0;
  border-bottom: 1px solid var(--line);
}
.nav-group-label {
  color: var(--ink-500);
  font: 11px var(--font-sans);
}
.admin-nav-group > div { margin-top: 4px; }
.admin-nav-group a {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 5px;
  padding: 7px 9px;
  margin: 2px 0;
  border-left: 2px solid transparent;
  color: var(--ink-700);
  font: 14px var(--font-sans);
}
.admin-nav-group small { font-size: 10px; color: var(--ink-500); }
.admin-nav-group a:hover { color: var(--blue-700); }
.admin-nav-group a.active {
  color: var(--blue-700);
  background: var(--blue-50);
  border-left-color: var(--blue-600);
  font-weight: 650;
}
.permission-panel {
  justify-self: center;
  width: min(100%, 700px);
  margin: clamp(16px, 7vh, 72px) auto;
  padding: clamp(24px, 5vw, 56px);
  border-block: 3px double var(--line-strong);
  background: var(--surface);
}
.permission-panel h1,
.admin-body :deep(.desk-title) {
  margin: 0;
  font: 680 clamp(29px, 3.6vw, 50px)/1.15 var(--font-editorial);
  letter-spacing: -.035em;
  overflow-wrap: anywhere;
}
.permission-panel p {
  margin: 14px 0 24px;
  color: var(--ink-500);
  line-height: 1.75;
}
.admin-body { min-width: 0; }
.admin-body :deep(.page-wrap) { padding: 0; max-width: none; }
.admin-body :deep(.admin-subview-stack),
.admin-body :deep(.admin-plugins-view) {
  display: grid;
  gap: 32px;
  min-width: 0;
}
.admin-body :deep(.panel) {
  min-width: 0;
  padding: clamp(16px, 2.5vw, 32px);
  border: 0;
  border-block: 1px solid var(--line-strong);
  border-radius: 0;
  background: var(--surface);
  box-shadow: none;
}
.admin-body :deep(.panel:first-child) { border-top: 3px double var(--ink-700); }
.admin-body :deep(.section-head) {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}
.admin-body :deep(.section-head > div) { min-width: 0; }
.admin-body :deep(h2),
.admin-body :deep(h3),
.admin-body :deep(h4) {
  margin: 0 0 8px;
  font: 650 21px/1.35 var(--font-editorial);
  overflow-wrap: anywhere;
}
.admin-body :deep(h4) { font-size: 16px; }
.admin-body :deep(.section-head p),
.admin-body :deep(.soft-note) {
  margin: 7px 0 0;
  color: var(--ink-500);
  font-size: 13px;
  line-height: 1.75;
}
.admin-body :deep(.queue-table-filters) {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 160px), 1fr));
  gap: 10px 12px;
  align-items: end;
  margin: 0 0 22px;
  min-width: 0;
  padding: 10px 0 15px;
  border: 0;
  border-bottom: 1px solid var(--line);
}
.admin-body :deep(.queue-table-filters legend),
.admin-body :deep(.curation-editor-form legend),
.admin-body :deep(.form-chapter) {
  color: var(--ink-700);
  font: 650 14px/1.4 var(--font-editorial);
}
.admin-body :deep(.queue-table-filters legend) { padding: 0; }
.admin-body :deep(.desk-field) {
  display: grid;
  gap: 6px;
  min-width: 0;
  color: var(--ink-500);
  font: 12px var(--font-sans);
}
.admin-body :deep(.profile-editor-input) {
  min-width: 0;
  width: 100%;
  max-width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 2px;
  background: var(--paper);
  font: 13px/1.45 var(--font-sans);
}
.admin-body :deep(.admin-filter-toggle),
.admin-body :deep(.curation-editor-toggle) {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  font-size: 13px;
}
.admin-body :deep(.table-actions),
.admin-body :deep(.curation-editor-actions) {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.admin-body :deep(.desk-counts) {
  display: flex;
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 10px;
  color: var(--ink-500);
  font: 12px var(--font-sans);
}
.admin-body :deep(.desk-counts b) {
  color: var(--blue-700);
  font: 650 18px var(--font-editorial);
}
.admin-body :deep(.meta-list) {
  display: grid;
  gap: 12px;
  list-style: none;
  margin: 0;
  padding: 0;
}
.admin-body :deep(.meta-list li) {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  font-size: 12px;
}
.admin-body :deep(.meta-list li span),
.admin-body :deep(.review-feed-meta) { color: var(--ink-500); }
.admin-body :deep(.meta-list strong) { overflow-wrap: anywhere; text-align: right; }
.admin-body :deep(.review-feed),
.admin-body :deep(.admin-card-list) { display: grid; gap: 0; }
.admin-body :deep(.review-feed-item),
.admin-body :deep(.curation-editor-item) {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 18px;
  padding: 16px 0;
  border: 0;
  border-top: 1px solid var(--line);
  border-radius: 0;
  background: transparent;
}
.admin-body :deep(.review-feed-item > div:first-child),
.admin-body :deep(.curation-editor-item > div:first-child) { min-width: 0; overflow-wrap: anywhere; }
.admin-body :deep(.review-feed-item p),
.admin-body :deep(.curation-editor-item p) {
  margin: 5px 0;
  color: var(--ink-700);
  font-size: 13px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}
.admin-body :deep(.curation-editor-item strong) { font: 650 16px var(--font-editorial); }
.admin-body :deep(.curation-editor-item small),
.admin-body :deep(.review-feed-meta) { font-size: 12px; }
.admin-body :deep(.admin-form-grid) {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px 22px;
}
.admin-body :deep(.admin-form-head),
.admin-body :deep(.form-chapter),
.admin-body :deep(.form-wide),
.admin-body :deep(.curation-editor-meta),
.admin-body :deep(.curation-editor-form-actions) { grid-column: 1/-1; }
.admin-body :deep(.form-chapter) {
  margin: 7px 0 0;
  padding-top: 11px;
  border-top: 1px solid var(--line-strong);
}
.admin-body :deep(.admin-form-grid label) { display: grid; min-width: 0; gap: 6px; font-size: 13px; }
.admin-body :deep(.admin-form-grid .curation-editor-toggle) { display: flex; }
.admin-body :deep(.admin-form-grid input:not([type='checkbox'])),
.admin-body :deep(.admin-form-grid textarea) { width: 100%; min-width: 0; }
.admin-body :deep(.admin-form-grid textarea) { resize: vertical; min-height: 140px; }
.admin-body :deep(.admin-error) {
  padding: 20px;
  background: var(--danger-soft);
  border-left: 3px solid var(--danger);
  color: var(--danger-ink);
}
.admin-body :deep(.admin-error p) { margin: 0 0 12px; overflow-wrap: anywhere; }
@media (max-width: 960px) {
  .desk-workspace { grid-template-columns: minmax(0, 1fr); gap: 16px; }
  .admin-navigation { position: static; max-height: none; overflow: visible; padding: 0; border: 0; }
  .desk-menu-toggle {
    display: flex;
    width: 100%;
    min-height: 44px;
    padding: 9px 12px;
    border-block: 1px solid var(--line-strong);
    background: var(--surface);
    color: var(--ink-700);
    font-size: 13px;
  }
  .desk-menu-toggle strong { margin-left: auto; color: var(--blue-700); }
  .desk-sections { display: none; }
  .desk-sections.is-open {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    padding-block: 12px;
  }
  .desk-index-title { display: none; }
  .admin-nav-group a { min-height: 40px; align-items: center; }
}
@media (max-width: 600px) {
  .admin-body :deep(.admin-form-grid) { grid-template-columns: minmax(0, 1fr); }
  .admin-body :deep(.section-head),
  .admin-body :deep(.review-feed-item),
  .admin-body :deep(.curation-editor-item) { flex-direction: column; gap: 10px; }
  .admin-body :deep(.profile-editor-input),
  .admin-body :deep(.admin-form-grid input),
  .admin-body :deep(.admin-form-grid textarea) { font-size: 16px; }
}
</style>
