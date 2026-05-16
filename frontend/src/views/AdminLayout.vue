<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

interface AdminGroup {
  title: string
  items: Array<{
    name: string
    label: string
    meta?: string
  }>
}

const groups: AdminGroup[] = [
  {
    title: 'OVERVIEW',
    items: [
      { name: 'admin-dashboard', label: '仪表盘', meta: '概览' },
      { name: 'admin-system', label: '系统状态', meta: '运行' },
    ],
  },
  {
    title: 'GOVERNANCE',
    items: [
      { name: 'admin-plugins', label: '插件治理', meta: '插件' },
      { name: 'admin-versions', label: '版本治理', meta: '版本' },
      { name: 'admin-authors', label: '作者管理', meta: '作者' },
      { name: 'admin-comments', label: '评论审核', meta: '评论' },
    ],
  },
  {
    title: 'EDITORIAL',
    items: [
      { name: 'admin-curation', label: '精选配置', meta: '运营' },
      { name: 'admin-announcements', label: '公告管理', meta: '公告' },
    ],
  },
  {
    title: 'RECORDS',
    items: [
      { name: 'admin-audit', label: '审计日志', meta: '日志' },
      { name: 'admin-inbox', label: '后台信箱', meta: '消息' },
    ],
  },
]

const currentRouteName = computed(() => String(route.name || ''))
const currentTitle = computed(() => {
  for (const group of groups) {
    const hit = group.items.find((it) => it.name === currentRouteName.value)
    if (hit) return hit.label
  }
  return '管理后台'
})

function backToSite() {
  void router.push({ name: 'home' })
}
</script>

<template>
  <div class="admin-shell">
    <aside class="admin-side" aria-label="管理后台导航">
      <div class="admin-side-brand">
        <span class="kicker">ADMIN CONSOLE</span>
        <strong>Neo-MoFox</strong>
      </div>
      <nav class="admin-side-nav">
        <div v-for="group in groups" :key="group.title" class="admin-side-group">
          <h5>{{ group.title }}</h5>
          <RouterLink
            v-for="item in group.items"
            :key="item.name"
            :to="{ name: item.name }"
            :class="['admin-side-link', { 'is-active': currentRouteName === item.name }]"
          >
            <span class="lbl">{{ item.label }}</span>
            <small v-if="item.meta">{{ item.meta }}</small>
          </RouterLink>
        </div>
      </nav>
      <button type="button" class="admin-side-back" @click="backToSite">← 回到市场</button>
    </aside>

    <div class="admin-main">
      <header class="admin-main-head">
        <div class="admin-main-head-titles">
          <span class="kicker">{{ currentRouteName.replace('admin-', '').toUpperCase() }}</span>
          <h1>{{ currentTitle }}</h1>
        </div>
      </header>
      <div class="admin-main-body">
        <router-view />
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-shell {
  display: grid;
  grid-template-columns: 248px 1fr;
  align-items: stretch;
  min-height: calc(100vh - var(--topbar-h));
  background: var(--paper);
}

.admin-side {
  background: var(--ink-900);
  color: var(--ink-300);
  padding: var(--space-5) 0 var(--space-4);
  display: flex; flex-direction: column;
  position: sticky;
  top: var(--topbar-h);
  align-self: flex-start;
  height: calc(100vh - var(--topbar-h));
  overflow-y: auto;
}

.admin-side-brand {
  padding: 0 var(--space-5);
  margin-bottom: var(--space-4);
}
.admin-side-brand .kicker {
  display: block;
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 10.5px; color: var(--ink-300);
}
.admin-side-brand strong {
  display: block;
  font-family: var(--font-display); font-weight: 900;
  font-size: 18px; color: #fff;
  margin-top: 4px;
}

.admin-side-nav { flex: 1; display: grid; gap: var(--space-3); padding: 0 0 var(--space-3); }

.admin-side-group { display: grid; gap: 1px; padding: 8px 0; border-top: 1px solid #1a2940; margin-top: 8px; }
.admin-side-group:first-child { border-top: none; margin-top: 0; }

.admin-side-group h5 {
  margin: 0 0 6px;
  padding: 0 var(--space-5);
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 10.5px; color: #5a6c87;
}

.admin-side-link {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding: 8px var(--space-5); font-size: 13px;
  color: #cbd6e6;
  border-left: 3px solid transparent;
  transition: background var(--dur-fast), color var(--dur-fast), border-left-color var(--dur-fast);
}
.admin-side-link:hover { background: #0f1a2e; color: #fff; }
.admin-side-link.is-active {
  background: #0f1a2e; color: #fff;
  border-left-color: var(--coral);
  font-weight: 600;
}
.admin-side-link .lbl { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.admin-side-link small {
  font-family: var(--font-mono); font-size: 10.5px;
  background: rgba(255,255,255,0.04);
  padding: 1px 7px; border-radius: var(--radius-pill);
  color: var(--ink-300);
}
.admin-side-link.is-active small { background: var(--coral); color: #fff; }

.admin-side-back {
  margin: var(--space-3) var(--space-5) 0;
  padding: 8px 12px; border-radius: var(--radius-md);
  background: rgba(255,255,255,0.04);
  color: var(--ink-300); font-size: 12.5px; font-weight: 600;
  text-align: left;
  transition: background var(--dur-fast), color var(--dur-fast);
}
.admin-side-back:hover { background: rgba(255,255,255,0.1); color: #fff; }

.admin-main {
  min-width: 0;
  display: flex; flex-direction: column;
  background: var(--paper);
}

.admin-main-head {
  position: sticky; top: var(--topbar-h); z-index: 10;
  display: flex; justify-content: space-between; align-items: center; gap: var(--space-4);
  padding: var(--space-4) var(--space-7);
  background: var(--surface);
  border-bottom: 1px solid var(--line);
}
.admin-main-head .kicker {
  display: block;
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 10.5px; color: var(--ink-500);
}
.admin-main-head h1 {
  margin: 2px 0 0;
  font-family: var(--font-display); font-weight: 900;
  font-size: 22px; line-height: 1.1; color: var(--ink-900);
}
.admin-main-body {
  flex: 1;
  padding: var(--space-5) var(--space-7) var(--space-12);
  min-width: 0;
}

@media (max-width: 1023px) {
  .admin-shell { grid-template-columns: 1fr; }
  .admin-side {
    position: relative; top: 0; height: auto;
    width: 100%;
    flex-direction: row; flex-wrap: wrap;
    align-items: center; gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
  }
  .admin-side-brand { padding: 0; margin: 0 var(--space-3) 0 0; }
  .admin-side-nav { flex: 1; display: flex; flex-direction: row; flex-wrap: wrap; gap: 4px; padding: 0; }
  .admin-side-group { display: contents; }
  .admin-side-group h5 { display: none; }
  .admin-side-link {
    padding: 6px 10px; border-left: none;
    border-radius: var(--radius-pill);
    background: rgba(255,255,255,0.04);
    font-size: 12px;
  }
  .admin-side-link.is-active { background: var(--coral); color: #fff; }
  .admin-side-link.is-active small { background: rgba(0,0,0,0.2); }
  .admin-side-back { margin: 0; }
  .admin-main-head { padding: var(--space-3) var(--space-4); }
  .admin-main-body { padding: var(--space-4); }
}
</style>
