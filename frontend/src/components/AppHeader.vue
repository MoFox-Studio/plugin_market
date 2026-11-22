<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useToastStore } from '@/stores/toast';
import InboxBell from './InboxBell.vue';
import AppIcon from './AppIcon.vue';
import FoxMark from './FoxMark.vue';
defineEmits<{ 'toggle-sidebar': [] }>();
const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const toast = useToastStore();
const searchQuery = ref('');
const dark = ref(document.documentElement.dataset.theme === 'dark');
const label = computed(
  () =>
    (
      ({
        home: '发现 / DISCOVER',
        market: '插件目录',
        plugin: '插件档案',
        skills: '技能目录',
        skill: '技能档案',
        author: '社区人物',
        me: '创作工作台',
        'me-profile': '作者资料',
        inbox: '社区来信',
        status: '服务公报',
        notfound: '缺页',
      }) as Record<string, string>
    )[String(route.name)] ||
    (String(route.name).startsWith('admin') ? '编辑部' : '社区'),
);
function onSearch() {
  void router.push({
    name: 'market',
    query: searchQuery.value.trim() ? { q: searchQuery.value.trim() } : {},
  });
}
function toggleTheme() {
  dark.value = !dark.value;
  document.documentElement.dataset.theme = dark.value ? 'dark' : 'light';
  try {
    localStorage.setItem('mofox:theme', dark.value ? 'dark' : 'light');
  } catch {}
}
async function logout() {
  try {
    await auth.logout();
    toast.show('已退出登录', 'ok');
    void router.push('/');
  } catch (err) {
    toast.show(err instanceof Error ? err.message : '退出失败，请重试', 'bad');
  }
}
</script>
<template>
  <header class="market-header">
    <button
      class="header-menu icon-button"
      aria-label="打开导航"
      @click="$emit('toggle-sidebar')"
    >
      <AppIcon name="menu" />
    </button>
    <router-link to="/" class="header-brand"
      ><FoxMark :size="24" /><strong>MOFOX</strong></router-link
    >
    <span class="header-location"
      ><i v-if="route.name !== 'home'" class="running-title" lang="en"
        >MoFox Gazette</i
      >{{ label }}</span
    >
    <form class="header-search" role="search" @submit.prevent="onSearch">
      <AppIcon name="search" :size="16" /><input
        v-model="searchQuery"
        name="q"
        type="search"
        placeholder="搜索插件…"
        aria-label="搜索插件名称或功能"
      /><button type="submit" aria-label="提交搜索">↵</button>
    </form>
    <div class="header-actions">
      <button
        class="icon-button"
        :aria-label="dark ? '切换浅色主题' : '切换深色主题'"
        @click="toggleTheme"
      >
        <AppIcon :name="dark ? 'sun' : 'moon'" />
      </button>
      <span
        v-if="auth.loading && !auth.loaded"
        class="auth-pending"
        role="status"
        >确认身份…</span
      >
      <template v-else-if="auth.viewer"
        ><InboxBell /><router-link class="header-account" to="/me"
          ><img
            v-if="auth.viewer.avatar_url"
            :src="auth.viewer.avatar_url"
            alt=""
          /><span>{{ auth.viewer.display_name }}</span></router-link
        ><button class="header-logout" @click="logout">退出</button></template
      >
      <button
        v-else-if="auth.error"
        class="header-login"
        @click="auth.loadViewer(true)"
      >
        重试登录状态
      </button>
      <a v-else class="header-login" :href="auth.getLoginUrl()"
        ><AppIcon name="github" :size="18" /><span>登录</span></a
      >
    </div>
  </header>
</template>
