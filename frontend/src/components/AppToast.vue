<script setup lang="ts">
import { onBeforeUnmount, onMounted, shallowRef } from 'vue';
import { useToastStore } from '@/stores/toast';

const toast = useToastStore();
const labels = { info: '提示', success: '成功', warning: '警告', error: '错误' };
const portal = shallowRef<'body' | HTMLDialogElement>('body');
let observer: MutationObserver | undefined;
function syncPortal() {
  const dialogs = document.querySelectorAll<HTMLDialogElement>('dialog[open]');
  const focused = document.activeElement?.closest<HTMLDialogElement>('dialog[open]');
  portal.value = focused || dialogs[dialogs.length - 1] || 'body';
}
onMounted(() => {
  syncPortal();
  observer = new MutationObserver(records => {
    if (portal.value !== 'body' && !portal.value.isConnected) {
      syncPortal();
      return;
    }
    if (records.some(record => record.type === 'attributes' || [...record.addedNodes].some(
      node => node instanceof Element && (node.matches('dialog[open]') || node.querySelector('dialog[open]')),
    ))) syncPortal();
  });
  observer.observe(document.body, { attributes: true, attributeFilter: ['open'], subtree: true, childList: true });
});
onBeforeUnmount(() => { observer?.disconnect(); toast.clear(); });
</script>
<template>
  <Teleport :to="portal">
    <div class="feedback-viewport" role="log" aria-label="操作提示" aria-live="polite" aria-relevant="additions" aria-atomic="false">
      <TransitionGroup tag="ol" name="feedback" class="feedback-list">
        <li v-for="item in toast.notices" :key="item.id" class="feedback-item"
          :data-tone="item.tone" :class="{ 'is-leaving': item.removeAt !== null }">
          <div class="feedback-card">
            <svg class="feedback-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <g v-if="item.tone === 'success'"><rect x="3" y="3" width="18" height="18" rx="4"/><path d="m7.5 12 3 3 6-6"/></g>
              <g v-else-if="item.tone === 'warning'"><path d="m12 2.5 10 18h-20Z"/><path d="M12 8v5m0 3v.5"/></g>
              <g v-else-if="item.tone === 'error'"><path d="m8 2.5 8 0 5.5 5.5v8L16 21.5H8L2.5 16V8Z"/><path d="m8.7 8.7 6.6 6.6m0-6.6-6.6 6.6"/></g>
              <g v-else><circle cx="12" cy="12" r="9.5"/><path d="M12 11v6m0-10v.6"/></g>
            </svg>
            <span class="feedback-kind">{{ labels[item.tone] }}</span>
            <span class="feedback-text">{{ item.text }}</span>
          </div>
          <span v-if="item.removeAt !== null" class="feedback-particles" aria-hidden="true">
            <i v-for="n in 6" :key="n" />
          </span>
        </li>
      </TransitionGroup>
    </div>
  </Teleport>
</template>
<style scoped>
.feedback-viewport {
  position: fixed; z-index: 12100;
  top: calc(74px + env(safe-area-inset-top, 0px));
  inset-inline: max(12px, env(safe-area-inset-left, 0px)) max(12px, env(safe-area-inset-right, 0px));
  display: grid; justify-items: center; pointer-events: none;
}
.feedback-list {
  list-style: none; margin: 0; padding: 0; width: min(440px, 100%);
  display: grid; justify-items: center; gap: 7px;
}
.feedback-item {
  --feedback-ink: var(--blue-700); --feedback-paper: var(--blue-50);
  position: relative; max-width: 100%; min-width: 0;
}
.feedback-item[data-tone='success'] { --feedback-ink: var(--success-ink); --feedback-paper: var(--success-soft); }
.feedback-item[data-tone='warning'] { --feedback-ink: var(--warning-ink); --feedback-paper: var(--warning-soft); }
.feedback-item[data-tone='error'] { --feedback-ink: var(--danger-ink); --feedback-paper: var(--danger-soft); }
.feedback-card {
  display: grid; grid-template-columns: 20px auto minmax(0,1fr); align-items: start;
  gap: 9px; padding: 11px 17px 11px 12px; color: var(--ink-900);
  background: var(--feedback-paper); border: 1px solid color-mix(in srgb, var(--feedback-ink) 45%, var(--line));
  border-left: 3px solid var(--feedback-ink); border-radius: 3px; box-shadow: var(--shadow-2);
}
.feedback-icon { width: 20px; height: 20px; color: var(--feedback-ink); }
.feedback-kind { font-size: 11px; line-height: 20px; font-weight: 750; color: color-mix(in srgb, var(--feedback-ink) 78%, var(--ink-900)); }
.feedback-text { font-size: 14px; line-height: 1.5; font-weight: 600; overflow-wrap: anywhere; }
.feedback-enter-active, .feedback-move { transition: transform 160ms ease-out, opacity 160ms ease-out; }
.feedback-enter-from { transform: translateY(-5px); opacity: 0; }
.is-leaving .feedback-card { animation: feedback-fade 360ms ease-out both; }
.feedback-particles { position: absolute; inset: 0; color: var(--feedback-ink); }
.feedback-particles i {
  position: absolute; width: 3px; height: 3px; background: currentColor; border-radius: 1px;
  animation: feedback-dust 330ms ease-out both;
}
.feedback-particles i:nth-child(1) { top: 24%; left: 3%; --dx: -11px; --dy: -8px; }
.feedback-particles i:nth-child(2) { top: 76%; left: 6%; --dx: -9px; --dy: 6px; }
.feedback-particles i:nth-child(3) { top: 4%; left: 23%; --dx: -6px; --dy: -11px; }
.feedback-particles i:nth-child(4) { top: 8%; right: 17%; --dx: 6px; --dy: -9px; }
.feedback-particles i:nth-child(5) { top: 36%; right: 2%; --dx: 13px; --dy: -6px; }
.feedback-particles i:nth-child(6) { bottom: 16%; right: 8%; --dx: 8px; --dy: 7px; }
@keyframes feedback-fade { to { opacity: 0; transform: translateY(-4px); } }
@keyframes feedback-dust {
  0%, 12% { opacity: 0; transform: scale(.6); }
  32% { opacity: .8; }
  100% { opacity: 0; transform: translate(var(--dx), var(--dy)) scale(.25); }
}
@media (max-width: 760px) {
  .feedback-viewport { top: calc(68px + env(safe-area-inset-top, 0px)); }
  .feedback-card { padding: 10px 12px 10px 9px; gap: 7px; }
}
@media (prefers-reduced-motion: reduce) {
  .feedback-enter-active, .feedback-move { transition: none; }
  .is-leaving .feedback-card { animation: none; }
  .feedback-particles { display: none; }
}
:global(:root[data-reduced-motion='reduce'] .feedback-enter-active),
:global(:root[data-reduced-motion='reduce'] .feedback-move) { transition: none; }
:global(:root[data-reduced-motion='reduce'] .is-leaving .feedback-card) { animation: none; }
:global(:root[data-reduced-motion='reduce'] .feedback-particles) { display: none; }
</style>
