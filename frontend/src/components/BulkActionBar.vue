<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { BulkAction } from '@/types'

interface BulkActionOption {
  key: BulkAction
  label: string
  variant?: 'default' | 'danger'
  requireReason?: boolean
  parameterKey?: string
  parameterOptions?: Array<{ label: string; value: string }>
}

const props = defineProps<{
  selectedCount: number
  pending?: boolean
  actions: BulkActionOption[]
}>()

const emit = defineEmits<{
  (e: 'confirm', payload: { action: BulkAction; params: Record<string, unknown> }): void
  (e: 'cancel'): void
}>()

const active = ref<BulkActionOption | null>(null)
const confirmCount = ref('')
const reason = ref('')
const parameterValue = ref('')

const countMatches = computed(() => Number(confirmCount.value) === props.selectedCount)
const reasonValid = computed(() => !active.value?.requireReason || reason.value.trim().length > 0)
const canSubmit = computed(() => props.selectedCount > 0 && countMatches.value && reasonValid.value)

function openConfirm(action: BulkActionOption): void {
  active.value = action
  confirmCount.value = ''
  reason.value = ''
  parameterValue.value = action.parameterOptions?.[0]?.value || ''
}

function closeConfirm(): void {
  active.value = null
  emit('cancel')
}

function submit(): void {
  if (!active.value || !canSubmit.value) {
    return
  }
  const params: Record<string, unknown> = {}
  if (reason.value.trim()) {
    params.reason = reason.value.trim()
  }
  if (active.value.parameterKey && parameterValue.value) {
    params[active.value.parameterKey] = parameterValue.value
  }
  emit('confirm', { action: active.value.key, params })
  active.value = null
}

watch(() => props.selectedCount, (value) => {
  if (value === 0) {
    active.value = null
  }
})
</script>

<template>
  <transition name="bulk-bar">
    <section v-if="selectedCount > 0" class="bulk-action-bar">
      <div class="bulk-action-bar-main">
        <strong>已选择 {{ selectedCount }} 项</strong>
        <div class="bulk-action-bar-actions">
          <button
            v-for="action in actions"
            :key="action.key"
            type="button"
            :class="['btn', 'btn-sm', action.variant === 'danger' ? 'btn-danger' : 'btn-ghost']"
            :disabled="pending"
            @click="openConfirm(action)"
          >{{ action.label }}</button>
        </div>
      </div>

      <div v-if="active" class="bulk-action-bar-confirm">
        <strong>确认执行“{{ active.label }}”</strong>
        <p>请输入预期数量 {{ selectedCount }} 以继续。</p>
        <div class="bulk-action-bar-fields">
          <input v-model="confirmCount" class="profile-editor-input" type="number" :placeholder="String(selectedCount)">
          <input v-if="active.requireReason" v-model="reason" class="profile-editor-input" type="text" placeholder="填写操作原因（必填）">
          <input v-else v-model="reason" class="profile-editor-input" type="text" placeholder="填写操作原因（可选）">
          <select v-if="active.parameterOptions?.length && active.parameterKey" v-model="parameterValue" class="profile-editor-input">
            <option v-for="option in active.parameterOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
        </div>
        <div class="bulk-action-bar-actions">
          <button class="btn btn-primary btn-sm" type="button" :disabled="pending || !canSubmit" @click="submit">确认执行</button>
          <button class="btn btn-ghost btn-sm" type="button" :disabled="pending" @click="closeConfirm">取消</button>
        </div>
      </div>
    </section>
  </transition>
</template>