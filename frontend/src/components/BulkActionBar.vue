<script setup lang="ts">
import MarketSelect from '@/components/MarketSelect.vue';
import { computed, ref, watch } from 'vue';
import type { BulkAction } from '@/types';

interface BulkActionOption {
  key: BulkAction;
  label: string;
  variant?: 'default' | 'danger';
  requireReason?: boolean;
  parameterKey?: string;
  parameterOptions?: Array<{ label: string; value: string }>;
}

const props = defineProps<{
  selectedCount: number;
  pending?: boolean;
  actions: BulkActionOption[];
}>();

const emit = defineEmits<{
  (
    e: 'confirm',
    payload: { action: BulkAction; params: Record<string, unknown> },
  ): void;
  (e: 'cancel'): void;
}>();

const active = ref<BulkActionOption | null>(null);
const confirmCount = ref('');
const reason = ref('');
const parameterValue = ref('');

const countMatches = computed(
  () => Number(confirmCount.value) === props.selectedCount,
);
const reasonValid = computed(
  () => !active.value?.requireReason || reason.value.trim().length > 0,
);
const canSubmit = computed(
  () => props.selectedCount > 0 && countMatches.value && reasonValid.value,
);

function openConfirm(action: BulkActionOption): void {
  active.value = action;
  confirmCount.value = '';
  reason.value = '';
  parameterValue.value = action.parameterOptions?.[0]?.value || '';
}

function closeConfirm(): void {
  active.value = null;
  emit('cancel');
}

function submit(): void {
  if (props.pending || !active.value || !canSubmit.value) {
    return;
  }
  const params: Record<string, unknown> = {};
  if (reason.value.trim()) {
    params.reason = reason.value.trim();
  }
  if (active.value.parameterKey && parameterValue.value) {
    params[active.value.parameterKey] = parameterValue.value;
  }
  emit('confirm', { action: active.value.key, params });
  active.value = null;
}

watch(
  () => props.selectedCount,
  (value) => {
    if (value === 0) {
      active.value = null;
    }
  },
);
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
            :class="[
              'btn',
              'btn-sm',
              action.variant === 'danger' ? 'btn-danger' : 'btn-ghost',
            ]"
            :disabled="pending"
            @click="openConfirm(action)"
          >
            {{ action.label }}
          </button>
        </div>
      </div>

      <div v-if="active" class="bulk-action-bar-confirm">
        <strong>确认执行“{{ active.label }}”</strong>
        <p>请输入预期数量 {{ selectedCount }} 以继续。</p>
        <div class="bulk-action-bar-fields">
          <input
            aria-label="输入所选项目数量以确认"
            v-model="confirmCount"
            class="profile-editor-input"
            type="number"
            :placeholder="String(selectedCount)"
          />
          <input
            v-if="active.requireReason"
            v-model="reason"
            aria-label="操作原因"
            class="profile-editor-input"
            type="text"
            placeholder="填写操作原因（必填）"
          />
          <input
            v-else
            v-model="reason"
            aria-label="操作原因"
            class="profile-editor-input"
            type="text"
            placeholder="填写操作原因（可选）"
          />
          <MarketSelect
            v-if="active.parameterOptions?.length && active.parameterKey"
            v-model="parameterValue"
            class="profile-editor-input"
          >
            <option
              v-for="option in active.parameterOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </MarketSelect>
        </div>
        <div class="bulk-action-bar-actions">
          <button
            class="btn btn-primary btn-sm"
            type="button"
            :disabled="pending || !canSubmit"
            @click="submit"
          >
            确认执行
          </button>
          <button
            class="btn btn-ghost btn-sm"
            type="button"
            :disabled="pending"
            @click="closeConfirm"
          >
            取消
          </button>
        </div>
      </div>
    </section>
  </transition>
</template>
<style scoped>
.bulk-action-bar {
  position: sticky;
  bottom: 18px;
  z-index: 20;
  padding: 18px 22px;
  border: 1px solid var(--blue-300);
  border-left: 3px solid var(--blue-500);
  background: var(--surface-elevated);
  box-shadow: var(--shadow-2);
  border-radius: 4px;
}
.bulk-action-bar-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}
.bulk-action-bar-main strong {
  font-size: 13px;
  white-space: nowrap;
}
.bulk-action-bar-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.bulk-action-bar-confirm {
  padding-top: 20px;
  margin-top: 18px;
  border-top: 1px solid var(--line);
}
.bulk-action-bar-confirm > strong {
  font-size: 14px;
}
.bulk-action-bar-confirm p {
  color: var(--ink-500);
  font-size: 12px;
}
.bulk-action-bar-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 16px 0;
}
.bulk-action-bar-fields input,
.bulk-action-bar-fields select {
  flex: 1;
  min-width: 140px;
  padding: 10px;
  border: 1px solid var(--line);
  background: var(--paper);
  border-radius: 4px;
}
.bulk-bar-enter-active,
.bulk-bar-leave-active {
  transition:
    opacity var(--dur-base),
    transform var(--dur-base);
}
.bulk-bar-enter-from,
.bulk-bar-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
@media (max-width: 700px) {
  .bulk-action-bar-main {
    flex-direction: column;
    align-items: flex-start;
  }
  .bulk-action-bar {
    bottom: 8px;
    padding: 16px;
  }
  .bulk-action-bar-fields input,
  .bulk-action-bar-fields select {
    font-size: 16px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .bulk-bar-enter-active,
  .bulk-bar-leave-active {
    transition: none;
  }
}
</style>
