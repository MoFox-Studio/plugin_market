<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    modelValue: string;
    disabled?: boolean;
    maxlength?: number;
  }>(),
  {
    disabled: false,
    maxlength: 2000,
  },
);

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
}>();

const remaining = computed(() => props.maxlength - props.modelValue.length);
const tooLong = computed(() => remaining.value < 0);

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

const previewHtml = computed(() => {
  const escaped = escapeHtml(props.modelValue);
  return escaped
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(
      /\[([^\]]+)\]\((https:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noreferrer noopener">$1</a>',
    )
    .replace(/\n/g, '<br>');
});
</script>

<template>
  <section class="bio-editor">
    <textarea
      class="bio-editor-textarea"
      aria-label="作者简介"
      :aria-invalid="tooLong"
      :value="modelValue"
      :maxlength="maxlength"
      :disabled="disabled"
      placeholder="用几句话介绍你在做什么，以及希望大家如何使用你的作品。"
      @input="
        emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)
      "
    ></textarea>
    <div class="bio-editor-foot">
      <span class="bio-editor-counter" :class="{ 'is-danger': tooLong }"
        >{{ remaining }} 字剩余</span
      >
      <p v-if="tooLong" class="bio-editor-error">
        简介不能超过 {{ maxlength }} 字。
      </p>
    </div>
    <div class="bio-editor-preview">
      <span class="bio-editor-preview-kicker">PREVIEW</span>
      <div
        class="bio-editor-preview-body"
        v-html="
          previewHtml || '<em class=&quot;placeholder&quot;>还没有内容</em>'
        "
      ></div>
    </div>
  </section>
</template>

<style scoped>
.bio-editor {
  display: grid;
  gap: 10px;
}
.bio-editor-textarea {
  width: 100%;
  min-height: 140px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 3px;
  background: var(--surface);
  font: 13px/1.8 var(--font-body);
  color: var(--ink-900);
  resize: vertical;
}
.bio-editor-textarea:focus {
  outline: 2px solid var(--blue-500);
  outline-offset: 2px;
}
.bio-editor-textarea:disabled {
  opacity: 0.6;
}
.bio-editor-foot {
  display: flex;
  justify-content: end;
  gap: 10px;
}
.bio-editor-counter {
  font: 10px var(--font-mono);
  color: var(--ink-500);
}
.bio-editor-counter.is-danger,
.bio-editor-error {
  color: var(--danger);
}
.bio-editor-error {
  margin: 0;
  font-size: 12px;
}
.bio-editor-preview {
  padding: 16px;
  background: var(--surface-soft);
  border: 1px solid var(--line);
  border-radius: 3px;
}
.bio-editor-preview-kicker {
  display: block;
  margin-bottom: 10px;
  font: 9px var(--font-mono);
  letter-spacing: 0.13em;
  color: var(--ink-500);
}
.bio-editor-preview-body {
  color: var(--ink-700);
  font-size: 13px;
  line-height: 1.8;
  overflow-wrap: anywhere;
}
.bio-editor-preview-body :deep(strong) {
  color: var(--ink-900);
}
.bio-editor-preview-body :deep(a) {
  color: var(--blue-500);
  text-decoration: underline;
  text-underline-offset: 3px;
}
.bio-editor-preview-body :deep(.placeholder) {
  color: var(--ink-500);
  font-style: normal;
}
</style>
