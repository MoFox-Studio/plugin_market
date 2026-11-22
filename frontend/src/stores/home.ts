import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import api from '@/api';
import type { MarketHome } from '@/types';

export const useHomeStore = defineStore('home', () => {
  const data = ref<MarketHome | null>(null);
  const loaded = ref(false);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const lastLoadedAt = ref<string | null>(null);
  let generation = 0;
  let pending: Promise<MarketHome | null> | null = null;

  const showcase = computed(() => data.value?.showcase || []);
  const featuredPlugins = computed(() => data.value?.featured_plugins || []);
  const trendingAuthors = computed(() => data.value?.trending_authors || []);
  const activeAnnouncements = computed(
    () => data.value?.active_announcements || [],
  );

  function loadHome(force = false): Promise<MarketHome | null> {
    if (pending && !force) return pending;
    if (!force && loaded.value && data.value) {
      return Promise.resolve(data.value);
    }
    const id = ++generation;
    loading.value = true;
    error.value = null;
    pending = (async () => {
      try {
        const response = await api.market.home();
        if (id !== generation) return null;
        data.value = response;
        loaded.value = true;
        lastLoadedAt.value = new Date().toISOString();
        return data.value;
      } catch (err) {
        if (id !== generation) return null;
        error.value =
          err instanceof Error ? err.message : 'Failed to load market home.';
        return data.value;
      } finally {
        if (id === generation) {
          loading.value = false;
          pending = null;
        }
      }
    })();
    return pending;
  }

  async function refresh(): Promise<MarketHome | null> {
    return await loadHome(true);
  }

  function invalidate(options?: { clearData?: boolean }): void {
    ++generation;
    pending = null;
    loading.value = false;
    loaded.value = false;
    error.value = null;
    if (options?.clearData) {
      data.value = null;
      lastLoadedAt.value = null;
    }
  }

  return {
    data,
    loaded,
    loading,
    error,
    lastLoadedAt,
    showcase,
    featuredPlugins,
    trendingAuthors,
    activeAnnouncements,
    loadHome,
    refresh,
    invalidate,
  };
});
