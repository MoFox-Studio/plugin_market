import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import api from '@/api';
import type { InboxMessage } from '@/types';

const POLL_INTERVAL_MS = 30_000;

export const useInboxStore = defineStore('inbox', () => {
  const unreadCount = ref(0);
  const messages = ref<InboxMessage[]>([]);
  const total = ref(0);
  const loadingMessages = ref(false);
  const loadingUnread = ref(false);
  const polling = ref(false);
  const lastLoadedAt = ref<string | null>(null);

  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let visibilityBound = false;
  let identityVersion = 0;
  let messageVersion = 0;
  let unreadVersion = 0;

  const unreadBadge = computed(() =>
    unreadCount.value > 99 ? '99+' : String(unreadCount.value),
  );
  const hasUnread = computed(() => unreadCount.value > 0);

  function stopTimer(): void {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function loadUnreadCount(): Promise<number> {
    const id = ++unreadVersion;
    const identity = identityVersion;
    loadingUnread.value = true;
    try {
      const result = await api.inbox.unreadCount();
      if (identity !== identityVersion || id !== unreadVersion)
        return unreadCount.value;
      unreadCount.value = result.count || 0;
      return unreadCount.value;
    } catch {
      return unreadCount.value;
    } finally {
      if (identity === identityVersion && id === unreadVersion) {
        loadingUnread.value = false;
        lastLoadedAt.value = new Date().toISOString();
      }
    }
  }

  async function loadMessages(query?: {
    type?: string;
    offset?: number;
    limit?: number;
  }): Promise<InboxMessage[]> {
    const id = ++messageVersion;
    const identity = identityVersion;
    loadingMessages.value = true;
    try {
      const result = await api.inbox.list(query);
      if (identity !== identityVersion || id !== messageVersion) return [];
      messages.value = result.items || [];
      total.value = result.total || 0;
      return messages.value;
    } finally {
      if (identity === identityVersion && id === messageVersion) {
        loadingMessages.value = false;
        lastLoadedAt.value = new Date().toISOString();
      }
    }
  }

  async function markRead(messageId: number): Promise<number> {
    const identity = identityVersion;
    const result = await api.inbox.markRead(messageId);
    if (identity !== identityVersion) return 0;
    const current = messages.value.find((item) => item.id === messageId);
    if (current && current.status === 'unread') {
      current.status = 'read';
      current.read_at = new Date().toISOString();
      unreadCount.value = Math.max(0, unreadCount.value - 1);
    }
    return result.updated || 0;
  }

  async function markAllRead(): Promise<number> {
    const identity = identityVersion;
    const result = await api.inbox.markAllRead();
    if (identity !== identityVersion) return 0;
    messages.value = messages.value.map((item) =>
      item.status === 'unread'
        ? { ...item, status: 'read', read_at: new Date().toISOString() }
        : item,
    );
    unreadCount.value = 0;
    return result.updated || 0;
  }

  function onVisibilityChange(): void {
    if (typeof document === 'undefined') {
      return;
    }

    if (document.hidden) {
      stopTimer();
      return;
    }

    void loadUnreadCount();
    if (polling.value && pollTimer === null) {
      pollTimer = setInterval(() => {
        void loadUnreadCount();
      }, POLL_INTERVAL_MS);
    }
  }

  function startPolling(): void {
    polling.value = true;

    if (typeof document !== 'undefined' && !visibilityBound) {
      document.addEventListener('visibilitychange', onVisibilityChange);
      visibilityBound = true;
    }

    if (typeof document !== 'undefined' && document.hidden) {
      stopTimer();
      return;
    }

    void loadUnreadCount();
    if (pollTimer === null) {
      pollTimer = setInterval(() => {
        void loadUnreadCount();
      }, POLL_INTERVAL_MS);
    }
  }

  function stopPolling(options?: { clearState?: boolean }): void {
    polling.value = false;
    stopTimer();

    if (typeof document !== 'undefined' && visibilityBound) {
      document.removeEventListener('visibilitychange', onVisibilityChange);
      visibilityBound = false;
    }

    if (options?.clearState) {
      ++identityVersion;
      ++messageVersion;
      ++unreadVersion;
      loadingMessages.value = false;
      loadingUnread.value = false;
      unreadCount.value = 0;
      messages.value = [];
      total.value = 0;
      lastLoadedAt.value = null;
    }
  }

  return {
    unreadCount,
    unreadBadge,
    hasUnread,
    messages,
    total,
    loadingMessages,
    loadingUnread,
    polling,
    lastLoadedAt,
    loadUnreadCount,
    loadMessages,
    markRead,
    markAllRead,
    startPolling,
    stopPolling,
  };
});
