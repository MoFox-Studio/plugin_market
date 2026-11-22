<script setup lang="ts">
import { computed } from 'vue';
import type { InboxMessage } from '@/types';
import { formatRelative } from '@/utils/format';

const props = defineProps<{
  message: InboxMessage;
  busy?: boolean;
}>();

const emit = defineEmits<{
  (e: 'open', message: InboxMessage): void;
}>();

const typeLabel = computed(() => {
  const labels: Record<string, string> = {
    mention: '@ 提及',
    reply: '回复',
    governance: '治理',
    announcement: '公告',
    author_activity: '作者动态',
    plugin_activity: '插件动态',
    system: '系统',
  };
  return labels[props.message.type] || props.message.type;
});

const sourceLabel = computed(() => {
  if (props.message.source?.display_name) {
    return props.message.source.display_name;
  }
  if (props.message.source?.github_login) {
    return `@${props.message.source.github_login}`;
  }
  return 'MoFox';
});

const previewText = computed(() => {
  if (props.message.status === 'revoked' && props.message.type === 'mention') {
    return '引用的评论已被删除。';
  }
  return props.message.preview || '打开查看详情。';
});
</script>

<template>
  <button
    type="button"
    class="inbox-item"
    :class="[
      `is-${message.type}`,
      { 'is-unread': message.status === 'unread' },
    ]"
    :disabled="busy"
    @click="$emit('open', message)"
  >
    <span class="inbox-item-marker" aria-hidden="true">{{
      message.status === 'unread' ? '●' : '○'
    }}</span>
    <div class="inbox-item-content">
      <div class="inbox-item-head">
        <span class="inbox-item-type">{{ typeLabel }}</span>
        <span class="inbox-item-time">{{
          formatRelative(message.created_at)
        }}</span>
      </div>
      <div class="inbox-item-body">
        <strong>{{ sourceLabel }}</strong>
        <p>{{ previewText }}</p>
      </div>
    </div>
    <span class="inbox-item-arrow" aria-hidden="true">↗</span>
  </button>
</template>
<style scoped>
.inbox-item {
  width: 100%;
  display: flex;
  gap: 18px;
  align-items: flex-start;
  text-align: left;
  padding: 24px;
  border-bottom: 1px solid var(--line-soft);
  background: transparent;
  transition: background var(--dur-fast);
}
.inbox-item:last-child {
  border-bottom: 0;
}
.inbox-item:hover {
  background: var(--surface-soft);
}
.inbox-item.is-unread {
  background: var(--blue-50);
}
.inbox-item-marker {
  color: var(--ink-300);
  font-size: 9px;
  padding-top: 6px;
}
.is-unread .inbox-item-marker {
  color: var(--blue-500);
}
.inbox-item-content {
  flex: 1;
  min-width: 0;
}
.inbox-item-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.inbox-item-type {
  color: var(--blue-600);
  font: 10px var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.inbox-item-time {
  color: var(--ink-500);
  font-size: 11px;
}
.inbox-item-body strong {
  font-size: 14px;
  font-weight: 650;
}
.inbox-item-body p {
  font-size: 13px;
  color: var(--ink-500);
  line-height: 1.8;
  margin: 7px 0 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.inbox-item-arrow {
  color: var(--ink-300);
  padding-top: 3px;
}
.inbox-item:focus-visible {
  outline: 2px solid var(--blue-500);
  outline-offset: -3px;
}
@media (max-width: 600px) {
  .inbox-item {
    padding: 20px 16px;
    gap: 12px;
  }
  .inbox-item-time {
    font-size: 10px;
  }
}
</style>
