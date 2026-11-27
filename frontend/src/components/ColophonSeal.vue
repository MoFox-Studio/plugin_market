<script setup lang="ts">
import { computed, onBeforeUnmount, ref, useId } from 'vue';
import ImpressionArt from './ImpressionArt.vue';
import { impressions, type Impression } from '@/composables/rareImpressions';
import { lockBodyScroll } from '@/composables/bodyScrollLock';
const titleId = useId();
const descriptionId = useId();
const props = defineProps<{ print: Impression }>();
const plateNumber = computed(() => String(impressions.indexOf(props.print) + 1).padStart(2, '0'));
const dialog = ref<HTMLDialogElement>(),
  opener = ref<HTMLButtonElement>();
let releaseScroll: (() => void) | undefined;
function open() {
  if (!dialog.value || dialog.value.open) return;
  releaseScroll = lockBodyScroll();
  dialog.value.showModal();
}
function close() {
  dialog.value?.close();
}
function afterClose() {
  releaseScroll?.();
  releaseScroll = undefined;
  opener.value?.focus({ preventScroll: true });
}
onBeforeUnmount(() => releaseScroll?.());
</script>
<template>
  <div class="colophon-seal">
    <button
      class="seal-opener"
      ref="opener"
      type="button"
      aria-label="翻看藏印"
      aria-haspopup="dialog"
      @click="open"
    >
      <span class="seal-window" aria-hidden="true">
        <ImpressionArt class="seal-art" :print="print" />
      </span>
      <span class="seal-caption"
        ><small>刊末藏印 · {{ String(impressions.indexOf(print) + 1).padStart(2, '0') }}</small
        ><strong>翻看藏印 <span aria-hidden="true">⊕</span></strong></span
      >
    </button>
    <dialog
      ref="dialog"
      class="print-drawer"
      :aria-labelledby="titleId"
      :aria-describedby="descriptionId"
      @close="afterClose"
      @click.self="close"
    >
      <div class="print-sheet">
        <header>
        <span>MoFox 市场报 <span class="print-series"> / 隐秘图集</span></span
          ><button type="button" aria-label="合上图版" autofocus @click="close">
            合上 ×
          </button>
        </header>
        <div class="print-spread">
          <figure class="print-artwork">
            <div class="plate-registration" aria-hidden="true"><span>图 {{ plateNumber }}</span><span>私人藏印</span></div>
            <ImpressionArt class="collector-print" :print="print" />
            <figcaption>{{ print.detail }}</figcaption>
          </figure>
          <div class="print-editorial">
            <span class="print-volume">藏书票 <b>{{ plateNumber }}</b></span>
            <span class="print-collection">{{ print.collection }}</span>
            <h2 :id="titleId">{{ print.name }}</h2>
            <p class="print-latin">{{ print.caption }}</p>
            <div class="print-rule" aria-hidden="true">✦</div>
            <p :id="descriptionId" class="print-description">{{ print.description }}</p>
            <span class="print-signature">隐秘图集</span>
          </div>
        </div>
      </div>
    </dialog>
  </div>
</template>
<style scoped>
.colophon-seal {
  width: min(100%, 240px);
  justify-self: end;
}
.seal-opener {
  display: block;
  width: 100%;
  padding: 0;
  text-align: start;
}
.seal-window {
  display: grid;
  place-items: center;
  position: relative;
  width: 100%;
  aspect-ratio: 320 / 260;
  background: var(--surface-soft);
  color: var(--botanical-ink);
}
.seal-window::before,
.seal-window::after {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  pointer-events: none;
  border-color: var(--line-strong);
  border-style: solid;
}
.seal-window::before {
  top: 6px;
  left: 6px;
  border-width: 1px 0 0 1px;
}
.seal-window::after {
  right: 6px;
  bottom: 6px;
  border-width: 0 1px 1px 0;
}
.seal-art {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.seal-caption {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  padding: 6px 1px;
  border-top: 1px solid var(--line-strong);
}
.seal-caption small {
  color: var(--ink-500);
  font: 11px/1.5 var(--font-reading);
}
.seal-caption strong {
  color: var(--blue-700);
  font: 600 12px/1.5 var(--font-sans);
}
@media (max-width: 700px) {
  .colophon-seal {
    justify-self: start;
    width: min(100%, 220px);
  }
}
.print-drawer {
  width: min(980px, calc(100% - 32px));
  max-height: calc(100dvh - 32px);
  margin: auto;
  padding: 0;
  border: 1px solid var(--line-strong);
  color: var(--ink-900);
  background: var(--surface);
}
.print-drawer::backdrop {
  background: var(--overlay-strong);
}
.print-sheet {
  padding: clamp(16px, 3vw, 28px);
}
.print-sheet header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-bottom: 6px;
  border-bottom: 3px double var(--ink-500);
  font: 11px/1.4 var(--font-mono);
  color: var(--ink-500);
}
.print-sheet header button {
  min-height: 40px;
  padding: 0 6px;
  color: var(--ink-900);
}
.print-sheet h2 {
  margin: 10px 0;
  font: 800 clamp(27px, 3vw, 38px)/1.3 var(--font-editorial);
}
.print-latin {
  margin: 0;
  color: var(--ink-700);
  font: italic 16px/1.4 var(--font-reading);
}
.collector-print {
  display: block;
  width: 100%;
  aspect-ratio: 4 / 3;
  max-height: min(54dvh, 460px);
  overflow: visible;
}
.print-spread {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  margin-top: 22px;
}
.print-artwork {
  margin: 0;
  padding-right: 26px;
  min-width: 0;
}
.plate-registration {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: var(--ink-500);
  font: 9px/1.6 var(--font-mono);
  letter-spacing: 1.5px;
}
.print-artwork figcaption {
  padding: 10px 0;
  border-top: 1px solid var(--line);
  color: var(--ink-500);
  text-align: center;
  font: 11px/1.7 var(--font-reading);
  letter-spacing: 1px;
}
.print-editorial {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  padding: 8px 0 14px 25px;
  border-left: 1px solid var(--line);
}
.print-volume {
  color: var(--ink-500);
  font: 9px/1.3 var(--font-mono);
  letter-spacing: 2px;
  margin-bottom: 22px;
}
.print-volume b {
  font: italic 32px/1 var(--font-reading);
  margin-left: 8px;
  color: var(--blue-700);
}
.print-collection {
  color: var(--blue-700);
  font: 11px/1.4 var(--font-reading);
  letter-spacing: 3px;
}
.print-rule {
  margin: 18px 0 9px;
  color: var(--blue-700);
}
.print-description {
  margin: 0;
  font: 13px/1.95 var(--font-reading);
  color: var(--ink-500);
}
.print-signature {
  margin-top: 20px;
  font: 27px/1.4 var(--font-script);
  color: var(--blue-700);
}
@media (max-width: 700px) {
  .print-spread { grid-template-columns: minmax(0, 1fr); margin-top: 14px; }
  .print-artwork { padding: 0; }
  .print-editorial { padding: 16px 0 0; border: 0; }
  .print-volume, .print-signature, .print-rule { display: none; }
  .print-sheet h2 { margin: 5px 0; font-size: 27px; }
  .print-description { margin-top: 10px; }
  .print-series { display: none; }
}
</style>
