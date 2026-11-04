<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue';
import {
  marketDialog,
  settleMarketDialog,
} from '@/composables/useMarketDialog';
import { lockBodyScroll } from '@/composables/bodyScrollLock';
import FoxMark from './FoxMark.vue';
const dialog = ref<HTMLDialogElement>(),
  input = ref<HTMLTextAreaElement>(),
  cancel = ref<HTMLButtonElement>();
const draft = ref('');
let release: (() => void) | undefined;
watch(
  marketDialog,
  async (request) => {
    draft.value = request?.initialValue || '';
    if (!request) {
      dialog.value?.close();
      release?.();
      release = undefined;
      return;
    }
    await nextTick();
    if (marketDialog.value !== request) return;
    release ||= lockBodyScroll();
    if (!dialog.value?.open) dialog.value?.showModal();
    (request.mode === 'prompt' ? input.value : cancel.value)?.focus();
  },
  { flush: 'post', immediate: true },
);
function submit() {
  settleMarketDialog(
    marketDialog.value?.mode === 'prompt' ? draft.value : true,
  );
}
onBeforeUnmount(() => {
  release?.();
  settleMarketDialog(null);
});
</script>
<template>
  <dialog
    ref="dialog"
    class="market-action-dialog"
    aria-labelledby="market-action-title"
    aria-describedby="market-action-description"
    @cancel.prevent="settleMarketDialog(null)"
  >
    <form v-if="marketDialog" @submit.prevent="submit">
      <header>
        <FoxMark :size="30" /><span>MOFOX / ACTION REVIEW</span
        ><button
          type="button"
          class="icon-button"
          aria-label="关闭确认窗口"
          @click="settleMarketDialog(null)"
        >
          ×
        </button>
      </header>
      <div class="market-action-body">
        <span class="eyebrow">{{
          marketDialog.mode === 'prompt' ? '补充信息' : '操作确认'
        }}</span>
        <h2 id="market-action-title">
          {{ marketDialog.mode === 'prompt' ? '留下操作说明' : '确认后继续' }}
        </h2>
        <p id="market-action-description">{{ marketDialog.message }}</p>
        <label v-if="marketDialog.mode === 'prompt'"
          >操作原因 <small>可选</small
          ><textarea
            ref="input"
            v-model="draft"
            maxlength="1000"
            rows="4"
            placeholder="填写原因，便于后续查阅…"
          />
        </label>
      </div>
      <footer>
        <button
          ref="cancel"
          class="btn btn-ghost"
          type="button"
          @click="settleMarketDialog(null)"
        >
          取消</button
        ><button class="btn btn-primary" type="submit">
          {{ marketDialog.mode === 'prompt' ? '保存并继续' : '确认操作' }} ↗
        </button>
      </footer>
    </form>
  </dialog>
</template>
<style scoped>
.market-action-dialog {
  width: min(480px, calc(100vw - 32px));
  max-height: calc(100dvh - 32px);
  padding: 0;
  border: 1px solid var(--line-strong);
  border-top: 3px solid var(--blue-500);
  border-radius: 3px;
  background: var(--surface);
  color: var(--ink-900);
  box-shadow: var(--shadow-3);
}
.market-action-dialog::backdrop {
  background: var(--overlay-strong);
  backdrop-filter: blur(5px);
}
.market-action-dialog header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 22px;
  border-bottom: 1px solid var(--line);
}
.market-action-dialog header > span {
  color: var(--ink-500);
  font: 9px var(--font-mono);
  letter-spacing: 0.08em;
}
.market-action-dialog header > button {
  margin-left: auto;
  font-size: 20px;
}
.market-action-body {
  padding: 28px;
}
.market-action-body h2 {
  font-size: 26px;
  margin: 12px 0;
}
.market-action-body p {
  color: var(--ink-700);
  line-height: 1.8;
  overflow-wrap: anywhere;
}
.market-action-body label {
  display: grid;
  gap: 10px;
  margin-top: 24px;
  font-size: 12px;
}
.market-action-body small {
  color: var(--ink-500);
}
.market-action-body textarea {
  width: 100%;
  box-sizing: border-box;
}
.market-action-dialog footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 18px 28px;
  border-top: 1px solid var(--line);
  background: var(--surface-soft);
}
</style>
