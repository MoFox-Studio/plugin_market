<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useInboxStore } from '@/stores/inbox'
import type { InboxMessage, InboxMessageType } from '@/types'
import InboxItem from '@/components/InboxItem.vue'
import EmptyState from '@/components/EmptyState.vue'

const props = withDefaults(defineProps<{
  pageSize?: number
  eager?: boolean
}>(), {
  pageSize: 20,
  eager: false,
})

const emit = defineEmits<{
  (e: 'navigated', message: InboxMessage): void
}>()

const router = useRouter()
const inbox = useInboxStore()

const type = ref<string>('')
const offset = ref(0)
const openingId = ref<number | null>(null)

const typeOptions: Array<{ label: string; value: '' | InboxMessageType }> = [
  { label: '全部类型', value: '' },
  { label: '@ 提及', value: 'mention' },
  { label: '回复', value: 'reply' },
  { label: '治理', value: 'governance' },
  { label: '公告', value: 'announcement' },
  { label: '作者动态', value: 'author_activity' },
  { label: '插件动态', value: 'plugin_activity' },
  { label: '系统', value: 'system' },
]

const page = computed(() => Math.floor(offset.value / props.pageSize) + 1)
const totalPages = computed(() => Math.max(1, Math.ceil(inbox.total / props.pageSize)))
const canPrev = computed(() => offset.value > 0)
const canNext = computed(() => offset.value + props.pageSize < inbox.total)

async function loadPage(): Promise<void> {
  await inbox.loadMessages({
    type: type.value || undefined,
    offset: offset.value,
    limit: props.pageSize,
  })
}

function gotoPage(nextPage: number): void {
  offset.value = Math.max(0, (nextPage - 1) * props.pageSize)
}

function targetForMessage(message: InboxMessage) {
  if (message.link?.kind === 'comment' && message.link.plugin_id) {
    return {
      name: 'plugin',
      params: { id: message.link.plugin_id },
      hash: message.link.comment_id ? `#comment-${message.link.comment_id}` : '',
    }
  }
  if (message.link?.kind === 'plugin' && message.link.plugin_id) {
    return {
      name: 'plugin',
      params: { id: message.link.plugin_id },
    }
  }
  if (message.link?.kind === 'announcement') {
    return {
      name: 'inbox',
      query: {
        announcement: String(message.link.announcement_id || message.related_announcement_id || ''),
      },
    }
  }
  return { name: 'me', hash: '#me-overview' }
}

async function openMessage(message: InboxMessage): Promise<void> {
  openingId.value = message.id
  try {
    if (message.status === 'unread') {
      await inbox.markRead(message.id)
    }
    await router.push(targetForMessage(message))
    emit('navigated', message)
  } finally {
    openingId.value = null
  }
}

async function markAllRead(): Promise<void> {
  await inbox.markAllRead()
}

watch(type, () => {
  offset.value = 0
  void loadPage()
})

watch(offset, () => {
  void loadPage()
})

onMounted(() => {
  if (props.eager) {
    void loadPage()
  }
})
</script>

<template>
  <section class="inbox-list">
    <div class="inbox-list-toolbar">
      <label class="inbox-list-filter">
        <span>筛选</span>
        <select v-model="type">
          <option v-for="option in typeOptions" :key="option.label" :value="option.value">{{ option.label }}</option>
        </select>
      </label>
      <button
        type="button"
        class="btn btn-ghost btn-sm"
        :disabled="!inbox.hasUnread"
        @click="markAllRead"
      >全部已读</button>
    </div>

    <div v-if="inbox.loadingMessages" class="inbox-list-state">加载信箱中…</div>
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
      <EmptyState title="暂无消息" message="新的提及、回复、治理通知、作者动态和插件动态会出现在这里。" />
    </div>

    <div class="inbox-list-pagination">
      <small>第 {{ page }} / {{ totalPages }} 页 · 共 {{ inbox.total }} 条</small>
      <div class="inbox-list-pagination-actions">
        <button type="button" class="btn btn-ghost btn-sm" :disabled="!canPrev" @click="gotoPage(page - 1)">上一页</button>
        <button type="button" class="btn btn-ghost btn-sm" :disabled="!canNext" @click="gotoPage(page + 1)">下一页</button>
      </div>
    </div>
  </section>
</template>