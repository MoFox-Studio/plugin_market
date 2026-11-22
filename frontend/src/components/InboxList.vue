<script setup lang="ts">
import MarketSelect from '@/components/MarketSelect.vue';
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useInboxStore } from '@/stores/inbox';
import type { InboxMessage, InboxMessageType } from '@/types';
import InboxItem from '@/components/InboxItem.vue';
import PageSkeleton from '@/components/PageSkeleton.vue';
import { useToastStore } from '@/stores/toast';

const props = withDefaults(
  defineProps<{
    pageSize?: number;
    eager?: boolean;
  }>(),
  {
    pageSize: 20,
    eager: false,
  },
);

const emit = defineEmits<{
  (e: 'navigated', message: InboxMessage): void;
}>();

const toast = useToastStore();
const error = ref('');
const markingAll = ref(false);
let requestId = 0;
let disposed = false;
const router = useRouter();
const inbox = useInboxStore();

const type = ref<string>('');
const offset = ref(0);
const openingId = ref<number | null>(null);

const typeOptions: Array<{ label: string; value: '' | InboxMessageType }> = [
  { label: '全部类型', value: '' },
  { label: '@ 提及', value: 'mention' },
  { label: '回复', value: 'reply' },
  { label: '治理', value: 'governance' },
  { label: '公告', value: 'announcement' },
  { label: '作者动态', value: 'author_activity' },
  { label: '插件动态', value: 'plugin_activity' },
  { label: '系统', value: 'system' },
];

const page = computed(() => Math.floor(offset.value / props.pageSize) + 1);
const totalPages = computed(() =>
  Math.max(1, Math.ceil(inbox.total / props.pageSize)),
);
const canPrev = computed(() => offset.value > 0);
const canNext = computed(() => offset.value + props.pageSize < inbox.total);

async function loadPage(): Promise<void> {
  const version = ++requestId;
  error.value = '';
  try {
    await inbox.loadMessages({
      type: type.value || undefined,
      offset: offset.value,
      limit: props.pageSize,
    });
  } catch (err) {
    if (version === requestId)
      error.value = (err as Error).message || '消息暂时无法读取';
  }
}

function gotoPage(nextPage: number): void {
  offset.value = Math.max(0, (nextPage - 1) * props.pageSize);
}

function targetForMessage(message: InboxMessage) {
  if (message.link?.kind === 'comment' && message.link.plugin_id) {
    return {
      name: 'plugin',
      params: { id: message.link.plugin_id },
      hash: message.link.comment_id
        ? `#comment-${message.link.comment_id}`
        : '',
    };
  }
  if (message.link?.kind === 'plugin' && message.link.plugin_id) {
    return {
      name: 'plugin',
      params: { id: message.link.plugin_id },
    };
  }
  if (message.link?.kind === 'announcement') {
    return {
      name: 'inbox',
      query: {
        announcement: String(
          message.link.announcement_id || message.related_announcement_id || '',
        ),
      },
    };
  }
  return { name: 'me', hash: '#me-overview' };
}

async function openMessage(message: InboxMessage): Promise<void> {
  if (openingId.value !== null) return;
  openingId.value = message.id;
  try {
    if (message.status === 'unread') {
      await inbox.markRead(message.id);
    }
    if (disposed) return;
    await router.push(targetForMessage(message));
    emit('navigated', message);
  } catch (err) {
    if (!disposed)
      toast.show((err as Error).message || '无法打开消息，请重试', 'error');
  } finally {
    openingId.value = null;
  }
}

async function markAllRead(): Promise<void> {
  if (markingAll.value) return;
  markingAll.value = true;
  try {
    await inbox.markAllRead();
  } catch (err) {
    if (!disposed)
      toast.show((err as Error).message || '标记已读失败', 'error');
  } finally {
    markingAll.value = false;
  }
}

watch(type, () => {
  if (offset.value !== 0) offset.value = 0;
  else void loadPage();
});

watch(offset, () => {
  void loadPage();
});

onMounted(() => {
  if (props.eager) {
    void loadPage();
  }
});
onBeforeUnmount(() => {
  disposed = true;
  ++requestId;
});
</script>

<template>
  <section class="inbox-list">
    <div class="inbox-list-toolbar">
      <label class="inbox-list-filter">
        <span>筛选</span>
        <MarketSelect v-model="type">
          <option
            v-for="option in typeOptions"
            :key="option.label"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </MarketSelect>
      </label>
      <button
        type="button"
        class="btn btn-ghost btn-sm"
        :disabled="!inbox.hasUnread || markingAll"
        @click="markAllRead"
      >
        {{ markingAll ? '正在处理…' : '全部标为已读' }}
      </button>
    </div>

    <PageSkeleton v-if="inbox.loadingMessages" type="rows" :count="4" />
    <div v-else-if="error" class="inbox-error" role="status">
      <h3>消息暂时无法加载</h3>
      <p>{{ error }}</p>
      <button class="btn" @click="loadPage">重新加载</button>
    </div>
    <div v-else-if="inbox.messages.length" class="inbox-list-items">
      <InboxItem
        v-for="message in inbox.messages"
        :key="message.id"
        :message="message"
        :busy="openingId === message.id"
        @open="openMessage"
      />
    </div>
    <div v-else class="inbox-list-empty">
      <h3>{{ type ? '这一类暂时没有来信' : '暂时没有来信' }}</h3>
      <p>{{ type ? '可以切回全部类型，查看其他消息。' : '有人回复或提及你时，相关讨论会出现在这里。' }}</p>
      <button v-if="type" type="button" class="btn btn-ghost btn-sm" @click="type = ''">查看全部来信</button>
    </div>

    <div class="inbox-list-pagination">
      <small
        >第 {{ page }} / {{ totalPages }} 页 · 共 {{ inbox.total }} 条</small
      >
      <div class="inbox-list-pagination-actions">
        <button
          type="button"
          class="btn btn-ghost btn-sm"
          :disabled="!canPrev || inbox.loadingMessages"
          @click="gotoPage(page - 1)"
        >
          上一页
        </button>
        <button
          type="button"
          class="btn btn-ghost btn-sm"
          :disabled="!canNext || inbox.loadingMessages"
          @click="gotoPage(page + 1)"
        >
          下一页
        </button>
      </div>
    </div>
  </section>
</template>
<style scoped>
.inbox-list-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px;
  border-bottom: 1px solid var(--line);
}
.inbox-list-filter {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--ink-500);
}
.inbox-list-filter select {
  border: 1px solid var(--line);
  border-radius: 4px;
  background: var(--paper);
  padding: 9px 32px 9px 12px;
  color: var(--ink-900);
  min-width: 150px;
}
.inbox-list-items {
  display: grid;
}
.inbox-list-empty {
  padding: 32px 24px;
}
.inbox-list-empty h3 { margin: 0; font: 800 23px/1.4 var(--font-editorial); }
.inbox-list-empty p { margin: 9px 0; color: var(--ink-500); font-size: 13px; line-height: 1.8; }
.inbox-list-empty button { margin-top: 9px; }
.inbox-list-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-top: 1px solid var(--line);
  padding: 18px 24px;
}
.inbox-list-pagination small {
  color: var(--ink-500);
  font: 11px var(--font-mono);
}
.inbox-list-pagination-actions {
  display: flex;
  gap: 8px;
}
.inbox-error {
  padding: 32px;
  color: var(--danger-ink);
}
.inbox-error h3 {
  margin: 0 0 10px;
  font-size: 17px;
}
.inbox-error p {
  font-size: 13px;
  overflow-wrap: anywhere;
}
@media (max-width: 600px) {
  .inbox-list-toolbar,
  .inbox-list-pagination {
    padding: 16px;
    flex-wrap: wrap;
  }
  .inbox-list-filter select {
    font-size: 16px;
  }
  .inbox-list-filter > span {
    display: none;
  }
}
</style>
