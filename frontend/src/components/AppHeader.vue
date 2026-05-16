<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import InboxBell from '@/components/InboxBell.vue'

defineEmits<{
  (e: 'toggle-sidebar'): void
}>()

const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()

const searchQuery = ref('')

function onSearch() {
  const q = searchQuery.value.trim()
  void router.push({
    name: 'market',
    query: q ? { q } : {},
  })
}

async function onLogout() {
  await auth.logout()
  toast.show('已退出登录', 'ok')
  router.push('/')
}
</script>

<template>
  <header class="topbar">
    <router-link class="brand" to="/">
      <img class="brand-logo" src="/logo.png" alt="Neo-MoFox">
      <span class="brand-text">
        <b>Neo-MoFox</b>
        <span>Plugin Market</span>
      </span>
    </router-link>

    <form class="topbar-search" role="search" @submit.prevent="onSearch">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
      <input
        v-model="searchQuery"
        type="search"
        name="q"
        placeholder="搜索插件、作者、标签…"
        autocomplete="off"
      >
      <button type="submit" class="btn btn-primary btn-sm">搜索</button>
    </form>

    <nav class="topbar-nav">
      <router-link class="navlink" to="/" active-class="active" exact>推荐</router-link>
      <router-link class="navlink" to="/browse" active-class="active">浏览</router-link>
      <router-link class="navlink" to="/me" active-class="active">我的</router-link>
      <span class="auth-slot" data-auth-slot>
        <template v-if="auth.isAuthenticated && auth.viewer">
          <InboxBell />
          <router-link
            class="navlink navlink-profile"
            :to="`/author/${encodeURIComponent(auth.viewer.author_id)}`"
          >
            <img
              v-if="auth.viewer.avatar_url"
              class="auth-avatar"
              :src="auth.viewer.avatar_url"
              alt=""
            >
            <span
              v-else
              class="auth-avatar auth-avatar-fallback"
              aria-hidden="true"
            >{{ (auth.viewer.display_name || 'M').trim()[0]?.toUpperCase() || 'M' }}</span>
            <span class="auth-name">{{ auth.viewer.display_name }}</span>
          </router-link>
          <router-link v-if="auth.isAdmin" class="navlink" to="/admin">管理</router-link>
          <button class="btn btn-ghost btn-sm" @click.stop="onLogout">退出</button>
        </template>
        <template v-else>
          <a class="btn btn-primary btn-sm" :href="auth.getLoginUrl()">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>
            GitHub 登录
          </a>
        </template>
      </span>
    </nav>

    <button
      class="mobile-menu-toggle"
      aria-expanded="false"
      aria-label="打开导航"
      @click="$emit('toggle-sidebar')"
    >☰</button>
  </header>
</template>
