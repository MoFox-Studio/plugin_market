import { computed, ref } from 'vue';

export const booting = ref(true);
const navigation = ref(false);
const reads = ref(0);
const layoutReads = ref(0);
export const routeError = ref('');
export const navigationEpoch = ref(0);
export const routeBusy = computed(() => navigation.value || reads.value > 0);
// Restoration can depend on content below the fold (README, versions, inbox),
// without making those requests delay the global loading indicator.
export const scrollRestorationBusy = computed(
  () => navigation.value || layoutReads.value > 0,
);
export const BOOT_MINIMUM_MS = 2400;
const BOOT_REVEAL_MS = 200;
let finishRequested = false;
let holdTimer: number | undefined;
let revealTimer: number | undefined;

declare global {
  interface Window {
    __mofoxBoot?: { startedAt: number; stopWatch(): void; fail(): void };
  }
}

export function startNavigation() {
  navigationEpoch.value++;
  reads.value = 0;
  layoutReads.value = 0;
  routeError.value = '';
  navigation.value = true;
}
export function finishNavigation(error?: string) {
  navigation.value = false;
  if (error) routeError.value = error;
}
export function trackRead(path: string, method: string) {
  const relevant =
    method === 'GET' &&
    /\/api\/v1\/(market\/home|plugins(?:[/?]|$)|skills(?:[/?]|$)|authors(?:[/?]|$)|me\/(?:plugins|profile|subscriptions|follows))/.test(
      path,
    ) &&
    !/comments|ratings|versions|readme/.test(path);
  const affectsLayout =
    method === 'GET' &&
    /^\/api\/v1\/(market\/home(?:[/?]|$)|plugins(?:[/?]|$)|skills(?:[/?]|$)|authors(?:[/?]|$)|me\/(?:plugins|profile|subscriptions|follows|pins|skills|access-token)(?:[/?]|$)|admin(?:[/?]|$)|inbox\/messages(?:[/?]|$))/.test(
      path,
    );
  const ownEpoch = navigationEpoch.value;
  if (relevant) reads.value++;
  if (affectsLayout) layoutReads.value++;
  let done = false;
  return () => {
    if (!done && ownEpoch === navigationEpoch.value) {
      if (relevant) reads.value = Math.max(0, reads.value - 1);
      if (affectsLayout) layoutReads.value = Math.max(0, layoutReads.value - 1);
    }
    done = true;
  };
}
export function finishBoot() {
  if (finishRequested || !booting.value) return;
  const screen = document.getElementById('boot-screen');
  if (screen?.dataset.phase === 'failed') return;
  finishRequested = true;
  const watch = window.__mofoxBoot;
  watch?.stopWatch();

  function enterApp() {
    screen?.remove();
    document.getElementById('app')?.removeAttribute('inert');
    delete window.__mofoxBoot;
    booting.value = false;
  }
  if (!screen) return enterApp();

  const plate = screen;
  function reveal() {
    if (plate.dataset.phase === 'failed') return;
    plate.dataset.phase = 'leaving';
    plate.inert = true;
    const reduced = document.documentElement.dataset.reducedMotion === 'reduce'
      || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (reduced) enterApp();
    else revealTimer = window.setTimeout(enterApp, BOOT_REVEAL_MS);
  }
  // Count the time spent loading the initial route as part of the printed intro.
  const remaining = BOOT_MINIMUM_MS - (performance.now() - (watch?.startedAt ?? 0));
  if (remaining > 0) holdTimer = window.setTimeout(reveal, remaining);
  else reveal();
}

export function failBoot() {
  if (!booting.value) return;
  window.clearTimeout(holdTimer);
  window.clearTimeout(revealTimer);
  const screen = document.getElementById('boot-screen');
  if (screen) screen.inert = false;
  window.__mofoxBoot?.fail();
}
