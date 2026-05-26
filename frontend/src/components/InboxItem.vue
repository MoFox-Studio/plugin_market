<script setup lang="ts">
import { computed } from 'vue'
import type { InboxMessage } from '@/types'
import { formatRelative } from '@/utils/format'

const props = defineProps<{
  message: InboxMessage
  busy?: boolean
}>()

const emit = defineEmits<{
  (e: 'open', message: InboxMessage): void
}>()

const typeLabel = computed(() => {
  const labels: Record<string, string> = {
    mention: '@ 提及',
    reply: '回复',
    governance: '治理',
    announcement: '公告',
    author_activity: '作者动态',
    plugin_activity: '插件动态',
    system: '系统',
  }
  return labels[props.message.type] || props.message.type
})

const sourceLabel = computed(() => {
  if (props.message.source?.display_name) {
    return props.message.source.display_name
  }
  if (props.message.source?.github_login) {
    return `@${props.message.source.github_login}`
  }
  return 'MoFox'
})

const previewText = computed(() => {
  if (props.message.status === 'revoked' && props.message.type === 'mention') {
    return '引用的评论已被删除。'
  }
  return props.message.preview || '打开查看详情。'
})
</script>

<template>
  <button
    type="button"
    class="inbox-item"
    :class="[`is-${message.type}`, { 'is-unread': message.status === 'unread' }]"
    :disabled="busy"
    @click="$emit('open', message)"
  >
    <div class="inbox-item-head">
      <span class="inbox-item-type">{{ typeLabel }}</span>
      <span class="inbox-item-time">{{ formatRelative(message.created_at) }}</span>
    </div>
    <div class="inbox-item-body">
      <strong>{{ sourceLabel }}</strong>
      <p>{{ previewText }}</p>
    </div>
  </button>
</template>