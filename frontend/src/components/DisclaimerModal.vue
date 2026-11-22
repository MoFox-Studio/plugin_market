<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue';
const emit = defineEmits<{ resolved: [] }>();
const key = 'mofox_market_disclaimer_ack_v1';
const dialog = ref<HTMLDialogElement | null>(null);
const remaining = ref(3);
let timer: ReturnType<typeof setInterval> | null = null;
let previous: HTMLElement | null = null;
function close() {
  if (remaining.value > 0) return;
  try {
    localStorage.setItem(key, '1');
  } catch {}
  dialog.value?.close();
  previous?.focus();
  emit('resolved');
}
onMounted(async () => {
  let accepted = false;
  try {
    accepted = localStorage.getItem(key) === '1';
  } catch {}
  if (accepted) {
    emit('resolved');
    return;
  }
  await nextTick();
  previous = document.activeElement as HTMLElement;
  dialog.value?.showModal();
  timer = setInterval(() => {
    remaining.value--;
    if (remaining.value <= 0 && timer) clearInterval(timer);
  }, 1000);
});
onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
  dialog.value?.close();
});
</script>
<template>
  <dialog
    ref="dialog"
    class="welcome-dialog"
    aria-labelledby="disclaimer-title"
    @cancel.prevent
  >
    <span class="eyebrow">BEFORE YOU EXPLORE / 首次访问</span>
    <h2 id="disclaimer-title">开始探索之前</h2>
    <div class="welcome-copy">
      <p>
        插件市场中的所有插件均由用户自行上传，可能包含安全风险、兼容性问题或恶意代码。
      </p>
      <p>
        在安装或使用任何插件前，请务必确认你信任该插件的发布者，并且已经阅读过源码。
      </p>
      <p>
        因使用第三方插件造成的任何数据丢失、账号风险、设备损坏或其他损失，MoFox-Studio
        不承担责任。
      </p>
    </div>
    <div class="welcome-bottom">
      <span>MOFOX · PLUGIN MARKET</span
      ><button class="btn btn-primary" :disabled="remaining > 0" @click="close">
        {{
          remaining > 0
            ? '我已知悉（' + remaining + 's）'
            : '我已知悉，开始探索 ↗'
        }}
      </button>
    </div>
  </dialog>
</template>
<style scoped>
.welcome-dialog {
  width: min(560px, calc(100vw - 32px));
  padding: 32px;
  border: 1px solid var(--line);
  border-top: 3px solid var(--blue-500);
  background: var(--paper);
  color: var(--ink-900);
  max-height: 90dvh;
  overflow: auto;
}
.welcome-dialog::backdrop {
  background: var(--overlay-strong);
  backdrop-filter: blur(6px);
}
.welcome-dialog h2 {
  font-size: 30px;
  margin: 12px 0 24px;
  letter-spacing: -0.04em;
}
.welcome-copy {
  font-size: 14px;
  line-height: 1.9;
  color: var(--ink-700);
}
.welcome-bottom {
  margin-top: 28px;
  padding-top: 24px;
  border-top: 1px solid var(--line);
  display: flex;
  gap: 20px;
  align-items: center;
  justify-content: space-between;
}
.welcome-bottom > span {
  font: 8px var(--font-mono);
  color: var(--ink-500);
}
@media (max-width: 560px) {
  .welcome-dialog {
    padding: 24px;
  }
  .welcome-bottom {
    flex-wrap: wrap;
  }
  .welcome-bottom .btn {
    width: 100%;
  }
}
</style>
