import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import api from '@/api';
import type { AuthStatus, Author } from '@/types';

export const useAuthStore = defineStore('auth', () => {
  const viewer = ref<Author | null>(null);
  const loading = ref(false);
  const loaded = ref(false);
  const error = ref('');
  let generation = 0;
  let pending: Promise<void> | null = null;
  const isAuthenticated = computed(() => !!viewer.value);
  const isAdmin = computed(() => viewer.value?.is_admin === true);
  function loadViewer(force = false): Promise<void> {
    if (pending && !force) return pending;
    if (loaded.value && !force) return Promise.resolve();
    const id = ++generation;
    loading.value = true;
    error.value = '';
    pending = (async () => {
      try {
        const auth = await api.get<AuthStatus>('/api/v1/me');
        if (id !== generation) return;
        viewer.value = auth?.authenticated ? (auth.user ?? null) : null;
        loaded.value = true;
      } catch (err) {
        if (id !== generation) return;
        viewer.value = null;
        error.value = err instanceof Error ? err.message : '身份确认失败';
      } finally {
        if (id === generation) {
          loading.value = false;
          pending = null;
        }
      }
    })();
    return pending;
  }
  async function logout(): Promise<void> {
    await api.post('/api/v1/auth/logout');
    ++generation;
    pending = null;
    loading.value = false;
    loaded.value = true;
    viewer.value = null;
  }
  function getLoginUrl(redirectTo?: string): string {
    const rd = encodeURIComponent(
      redirectTo || location.pathname + location.search + location.hash,
    );
    return `/api/v1/auth/github/login?redirect_to=${rd}`;
  }
  return {
    viewer,
    loading,
    loaded,
    error,
    isAuthenticated,
    isAdmin,
    loadViewer,
    logout,
    getLoginUrl,
  };
});
