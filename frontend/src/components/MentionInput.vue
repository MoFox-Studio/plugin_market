<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import api from '@/api'
import { useMentionsStore } from '@/stores/mentions'
import type { MentionCandidate } from '@/types'
import { MENTION_PATTERN } from '@/utils/mentions'

const props = withDefaults(defineProps<{
  modelValue: string
  placeholder?: string
  disabled?: boolean
  maxlength?: number
}>(), {
  placeholder: '',
  disabled: false,
  maxlength: 4000,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'update:mentionedAuthorIds', value: string[]): void
}>()

const mentions = useMentionsStore()

const textareaRef = ref<HTMLTextAreaElement | null>(null)
const open = ref(false)
const options = ref<MentionCandidate[]>([])
const activeIndex = ref(0)
const selectedByLogin = ref<Record<string, MentionCandidate>>({})
const triggerStart = ref<number | null>(null)

function syncMentionIds(content: string): void {
  const next: Record<string, MentionCandidate> = {}
  const pattern = new RegExp(MENTION_PATTERN)
  let match: RegExpExecArray | null = null

  while ((match = pattern.exec(content)) !== null) {
    const login = match[1].toLowerCase()
    const selected = selectedByLogin.value[login]
    if (selected) {
      next[login] = selected
      continue
    }
    const cached = mentions.getCached(login).find((candidate) => candidate.github_login.toLowerCase() === login)
    if (cached) {
      next[login] = cached
    }
  }

  selectedByLogin.value = next
  emit('update:mentionedAuthorIds', Object.values(next).map((item) => item.author_id))
}

function currentTrigger(content: string, caret: number): { start: number; prefix: string } | null {
  const beforeCaret = content.slice(0, caret)
  const marker = beforeCaret.match(/(^|[\s(])@([A-Za-z0-9][A-Za-z0-9-]{0,38})?$/)
  if (!marker || marker.index === undefined) {
    return null
  }
  return {
    start: marker.index + marker[1].length,
    prefix: marker[2] || '',
  }
}

async function refreshSuggestions(): Promise<void> {
  const element = textareaRef.value
  if (!element) {
    return
  }
  const trigger = currentTrigger(props.modelValue, element.selectionStart || 0)
  if (!trigger || !trigger.prefix) {
    open.value = false
    triggerStart.value = null
    options.value = []
    return
  }
  triggerStart.value = trigger.start
  options.value = await mentions.resolve(trigger.prefix, (prefix) => api.authors.search(prefix))
  activeIndex.value = 0
  open.value = options.value.length > 0
}

function updateValue(value: string): void {
  emit('update:modelValue', value)
  syncMentionIds(value)
}

function choose(candidate: MentionCandidate): void {
  const element = textareaRef.value
  if (!element || triggerStart.value === null) {
    return
  }
  const start = triggerStart.value
  const caret = element.selectionStart || start
  const nextValue = `${props.modelValue.slice(0, start)}@${candidate.github_login} ${props.modelValue.slice(caret)}`
  selectedByLogin.value = {
    ...selectedByLogin.value,
    [candidate.github_login.toLowerCase()]: candidate,
  }
  updateValue(nextValue)
  open.value = false
  void nextTick(() => {
    const nextCaret = start + candidate.github_login.length + 2
    textareaRef.value?.focus()
    textareaRef.value?.setSelectionRange(nextCaret, nextCaret)
  })
}

function onInput(event: Event): void {
  const target = event.target as HTMLTextAreaElement
  updateValue(target.value)
  void refreshSuggestions()
}

function onKeydown(event: KeyboardEvent): void {
  if (!open.value || !options.value.length) {
    return
  }
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    activeIndex.value = (activeIndex.value + 1) % options.value.length
    return
  }
  if (event.key === 'ArrowUp') {
    event.preventDefault()
    activeIndex.value = (activeIndex.value - 1 + options.value.length) % options.value.length
    return
  }
  if (event.key === 'Enter' || event.key === 'Tab') {
    event.preventDefault()
    choose(options.value[activeIndex.value])
    return
  }
  if (event.key === 'Escape') {
    open.value = false
  }
}

watch(() => props.modelValue, (value) => {
  syncMentionIds(value)
})
</script>

<template>
  <div class="mention-input">
    <textarea
      ref="textareaRef"
      :value="modelValue"
      :maxlength="maxlength"
      :placeholder="placeholder"
      :disabled="disabled"
      @input="onInput"
      @click="refreshSuggestions"
      @keyup="refreshSuggestions"
      @keydown="onKeydown"
    ></textarea>

    <div v-if="open" class="mention-input-popup" role="listbox" aria-label="提及候选">
      <button
        v-for="(candidate, index) in options"
        :key="candidate.author_id"
        type="button"
        class="mention-input-option"
        :class="{ 'is-active': index === activeIndex }"
        @mousedown.prevent="choose(candidate)"
      >
        <img v-if="candidate.avatar_url" :src="candidate.avatar_url" alt="">
        <span v-else class="mention-input-option-fallback">{{ candidate.display_name[0]?.toUpperCase() || '?' }}</span>
        <span class="mention-input-option-copy">
          <strong>{{ candidate.display_name }}</strong>
          <small>@{{ candidate.github_login }}</small>
        </span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.mention-input {
  position: relative;
  width: 100%;
}

.mention-input textarea {
  width: 100%;
  min-height: 132px;
  resize: vertical;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1.5px solid var(--line);
  background: var(--surface);
  color: var(--ink-900);
  font: inherit;
  line-height: 1.65;
  outline: none;
  transition: border-color var(--dur-fast), box-shadow var(--dur-fast), background var(--dur-fast);
}

.mention-input textarea:focus {
  border-color: var(--blue-500);
  box-shadow: 0 0 0 4px rgba(38, 168, 241, 0.12);
}

.mention-input textarea:disabled {
  background: var(--surface-soft);
  color: var(--ink-500);
  cursor: not-allowed;
}

.mention-input-popup {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  z-index: 20;
  width: min(360px, 100%);
  max-height: 240px;
  overflow-y: auto;
  padding: 6px;
  display: grid;
  gap: 4px;
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.98);
  box-shadow: var(--shadow-3);
  backdrop-filter: blur(10px);
}

.mention-input-option {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  width: 100%;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  text-align: left;
  transition: background var(--dur-fast), transform var(--dur-fast);
}

.mention-input-option:hover,
.mention-input-option.is-active {
  background: var(--blue-100);
}

.mention-input-option.is-active {
  transform: translateX(2px);
}

.mention-input-option img,
.mention-input-option-fallback {
  width: 36px;
  height: 36px;
  border-radius: 50%;
}

.mention-input-option img {
  object-fit: cover;
}

.mention-input-option-fallback {
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, var(--blue-500), var(--blue-700));
  color: var(--ink-on-blue);
  font-family: var(--font-display);
  font-weight: 900;
}

.mention-input-option-copy {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.mention-input-option-copy strong {
  color: var(--ink-900);
  font-size: 13px;
  line-height: 1.2;
}

.mention-input-option-copy small {
  color: var(--ink-500);
  font-family: var(--font-mono);
  font-size: 11px;
}

@media (max-width: 640px) {
  .mention-input-popup {
    width: 100%;
  }
}
</style>