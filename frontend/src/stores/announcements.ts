import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import api from '@/api';
import type { Announcement } from '@/types';

const STORAGE_KEY = 'plugin-market:announcement-dismissals:v1';

function loadDismissedCache(): Record<number, number> {
  if (typeof window === 'undefined') {
    return {};
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {};
    }
    return JSON.parse(raw) as Record<number, number>;
  } catch {
    return {};
  }
}

export const useAnnouncementsStore = defineStore('announcements', () => {
  const items = ref<Announcement[]>([]);
  const loaded = ref(false);
  const loading = ref(false);
  let generation = 0;
  const dismissedTokens = ref<Record<number, number>>(loadDismissedCache());

  const visibleItems = computed(() =>
    items.value.filter((item) => {
      const token = dismissedTokens.value[item.id];
      return token === undefined || token < item.dismiss_token;
    }),
  );
  const activeBanners = computed(() =>
    visibleItems.value.filter((item) => item.display_mode === 'banner'),
  );
  const activeModals = computed(() =>
    visibleItems.value.filter((item) => item.display_mode === 'modal'),
  );

  function persistDismissedCache(): void {
    if (typeof window === 'undefined') {
      return;
    }
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(dismissedTokens.value),
      );
    } catch {}
  }

  async function loadActive(force = false): Promise<Announcement[]> {
    if (!force && loaded.value) {
      return items.value;
    }

    const id = ++generation;
    loading.value = true;
    try {
      const result = await api.announcements.active();
      if (id !== generation) return [];
      items.value = result;
      loaded.value = true;
      return items.value;
    } catch {
      if (id === generation) loaded.value = false;
      return [];
    } finally {
      if (id === generation) loading.value = false;
    }
  }

  function dismissLocal(announcementId: number, dismissToken: number): void {
    dismissedTokens.value = {
      ...dismissedTokens.value,
      [announcementId]: dismissToken,
    };
    persistDismissedCache();
  }

  async function dismiss(announcementId: number): Promise<void> {
    const result = await api.announcements.dismiss(announcementId);
    dismissLocal(result.announcement_id, result.dismiss_token);
  }

  function reset(): void {
    ++generation;
    loading.value = false;
    items.value = [];
    loaded.value = false;
  }

  return {
    items,
    loaded,
    loading,
    dismissedTokens,
    visibleItems,
    activeBanners,
    activeModals,
    loadActive,
    dismiss,
    dismissLocal,
    reset,
  };
});
