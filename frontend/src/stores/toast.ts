import { computed, onScopeDispose, ref } from 'vue';
import { defineStore } from 'pinia';

type Tone = 'info' | 'success' | 'warning' | 'error';
interface Notice {
  id: number;
  text: string;
  tone: Tone;
  readyAt: number;
  removeAt: number | null;
}
const LIMIT = 5;
const EXIT_GAP = 650;
const DISSOLVE = 360;
const tones: Record<string, Tone | undefined> = {
  ok: 'success', success: 'success', warn: 'warning', warning: 'warning',
  error: 'error', danger: 'error', bad: 'error',
};

function reducedMotion() {
  return typeof window !== 'undefined' && (
    document.documentElement.dataset.reducedMotion === 'reduce' ||
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  );
}

export const useToastStore = defineStore('toast', () => {
  const notices = ref<Notice[]>([]);
  const message = ref('');
  const kind = ref('');
  const visible = computed(() => notices.value.length > 0);
  let counter = 0;
  let nextExitAt = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;

  // One timer belongs to the oldest entry. New arrivals cannot restart its lifetime.
  function schedule() {
    clearTimeout(timer);
    timer = undefined;
    const oldest = notices.value[0];
    if (!oldest) {
      nextExitAt = 0;
      return;
    }
    const deadline = oldest.removeAt ?? Math.max(oldest.readyAt, nextExitAt);
    timer = setTimeout(() => {
      if (oldest.removeAt !== null) {
        notices.value.shift();
      } else {
        nextExitAt = Date.now() + EXIT_GAP;
        if (reducedMotion()) notices.value.shift();
        else oldest.removeAt = Date.now() + DISSOLVE;
      }
      schedule();
    }, Math.max(0, deadline - Date.now()));
  }

  function show(msg: string, type = ''): void {
    message.value = msg;
    kind.value = type;
    const lifetime = Math.max(3000, Math.min(8500, 1800 + msg.length * 65));
    notices.value.push({
      id: ++counter, text: msg, tone: tones[type] ?? 'info',
      readyAt: Date.now() + lifetime, removeAt: null,
    });
    if (notices.value.length > LIMIT) notices.value.shift();
    schedule();
  }
  function clear() {
    clearTimeout(timer);
    timer = undefined;
    nextExitAt = 0;
    notices.value = [];
  }
  onScopeDispose(clear);
  return { message, kind, visible, notices, show, clear };
});
