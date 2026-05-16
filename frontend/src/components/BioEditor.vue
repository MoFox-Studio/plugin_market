<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: string
  disabled?: boolean
  maxlength?: number
}>(), {
  disabled: false,
  maxlength: 2000,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const remaining = computed(() => props.maxlength - props.modelValue.length)
const tooLong = computed(() => remaining.value < 0)

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const previewHtml = computed(() => {
  const escaped = escapeHtml(props.modelValue)
  return escaped
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\((https:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer noopener">$1</a>')
    .replace(/\n/g, '<br>')
})
</script>

<template>
  <section class="bio-editor">
    <textarea
      class="bio-editor-textarea"
      :value="modelValue"
      :maxlength="maxlength"
      :disabled="disabled"
      placeholder="用几句话介绍你在做什么，以及希望大家如何使用你的作品。"
      @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    ></textarea>
    <div class="bio-editor-foot">
      <span class="bio-editor-counter" :class="{ 'is-danger': tooLong }">{{ remaining }} 字剩余</span>
      <p v-if="tooLong" class="bio-editor-error">Bio 不能超过 {{ maxlength }} 字。</p>
    </div>
    <div class="bio-editor-preview">
      <span class="bio-editor-preview-kicker">PREVIEW</span>
      <div class="bio-editor-preview-body" v-html="previewHtml || '<em class=&quot;placeholder&quot;>还没有内容</em>'"></div>
    </div>
  </section>
</template>

<style scoped>
.bio-editor { display: grid; gap: 8px; }

.bio-editor-textarea {
  width: 100%;
  min-height: 120px;
  padding: 10px 12px;
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--surface);
  font: inherit;
  font-size: 13.5px;
  color: var(--ink-900);
  line-height: 1.6;
  resize: vertical;
  transition: border-color var(--dur-fast), box-shadow var(--dur-fast);
}
.bio-editor-textarea:focus { outline: none; border-color: var(--blue-500); box-shadow: var(--ring); }
.bio-editor-textarea:disabled { opacity: 0.6; cursor: not-allowed; }

.bio-editor-foot {
  display: flex; justify-content: flex-end; align-items: center; gap: 8px;
}
.bio-editor-counter {
  font-family: var(--font-mono); font-size: 11px; color: var(--ink-500);
}
.bio-editor-counter.is-danger { color: var(--coral); font-weight: 700; }
.bio-editor-error { margin: 0; color: var(--coral); font-size: 12px; }

.bio-editor-preview {
  position: relative;
  padding: var(--space-3);
  background: var(--surface-soft);
  border: 1px dashed var(--line);
  border-radius: var(--radius-sm);
}
.bio-editor-preview-kicker {
  position: absolute; top: -10px; left: 12px;
  padding: 2px 8px;
  background: var(--surface);
  border-radius: var(--radius-pill);
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 10px; color: var(--ink-500);
}
.bio-editor-preview-body {
  color: var(--ink-700); font-size: 13px; line-height: 1.65;
  word-wrap: break-word;
}
.bio-editor-preview-body :deep(strong) { color: var(--ink-900); }
.bio-editor-preview-body :deep(a) {
  color: var(--blue-700);
  border-bottom: 1px solid var(--blue-300);
}
.bio-editor-preview-body :deep(.placeholder) {
  color: var(--ink-300); font-style: italic;
}
</style>