import { onBeforeUnmount, onMounted } from 'vue';

export interface MarketPointerRevealState {
  x: number;
  y: number;
  radius: number;
  active: boolean;
  local: boolean;
  surface: 'field' | 'paper' | 'control';
}
type Listener = (state: Readonly<MarketPointerRevealState>) => void;
const BASE_RADIUS = 110;
const MIN_RADIUS = 40;
const STOP_DELAY = 75;
const listeners = new Set<Listener>();
const state: MarketPointerRevealState = {
  x: 0,
  y: 0,
  radius: BASE_RADIUS,
  active: false,
  local: false,
  surface: 'field',
};
const properties = [
  '--market-pointer-x',
  '--market-pointer-y',
  '--market-pointer-radius',
  '--market-pointer-active',
];
let fine: MediaQueryList | null = null;
let reduced: MediaQueryList | null = null;
let preferenceObserver: MutationObserver | null = null;
let enabled = false;
let frame = 0;
let lastMove = 0;
let fromRadius = BASE_RADIUS;
let targetRadius = BASE_RADIUS;
let animationStart = 0;
let animationDuration = 0;

function publish() {
  const style = document.documentElement.style;
  style.setProperty(properties[0], `${state.x}px`);
  style.setProperty(properties[1], `${state.y}px`);
  style.setProperty(properties[2], `${state.radius.toFixed(3)}px`);
  style.setProperty(properties[3], state.active ? '1' : '0');
  for (const listener of listeners) listener(state);
}
function stopFrame() {
  if (frame) cancelAnimationFrame(frame);
  frame = 0;
}
function deactivate() {
  stopFrame();
  state.active = false;
  state.local = false;
  state.radius = fromRadius = targetRadius = BASE_RADIUS;
  lastMove = 0;
  publish();
}
function sampleRadius(now: number) {
  if (state.radius === targetRadius) return;
  const progress = Math.min(
    1,
    Math.max(0, (now - animationStart) / animationDuration),
  );
  const eased = 1 - (1 - progress) ** 3;
  state.radius =
    progress === 1
      ? targetRadius
      : fromRadius + (targetRadius - fromRadius) * eased;
}
function aimRadius(next: number, now: number) {
  if (Math.abs(next - targetRadius) < 0.1) return;
  sampleRadius(now);
  fromRadius = state.radius;
  targetRadius = next;
  animationStart = now;
  animationDuration = next < state.radius ? 80 : 180;
}
function animate(now: number) {
  frame = 0;
  if (!state.active || !enabled) return;
  if (now - lastMove >= STOP_DELAY) aimRadius(BASE_RADIUS, now);
  sampleRadius(now);
  publish();
  // A settled stationary lens does not keep the rendering loop alive.
  if (state.radius !== targetRadius || targetRadius !== BASE_RADIUS)
    frame = requestAnimationFrame(animate);
}
function radiusForSpeed(speed: number) {
  const t = Math.max(0, Math.min(1, (speed - 0.08) / 1.72));
  const eased = t * t * (3 - 2 * t);
  return BASE_RADIUS - (BASE_RADIUS - MIN_RADIUS) * eased;
}
function inspectTarget(target: EventTarget | null) {
  const element = target instanceof Element ? target : null;
  state.local = Boolean(element?.closest('[data-pointer-reveal-local]'));
  const link = element?.closest('a[href]');
  const inlineLink = link && !link.matches('.plugin-card, .skill-card, .recommendation-card__link');
  if (inlineLink || element?.closest('button, input, textarea, select, [contenteditable="true"], [role="listbox"], [role="dialog"], dialog, nav, .market-header, pre, code, img, video')) {
    state.surface = 'control';
  } else if (element?.closest('article, table, .panel, .catalog-panel, .plugin-card, .skill-card, .me-card, .me-sub-card, .identity-strip, .access-panel')) {
    state.surface = 'paper';
  } else {
    state.surface = 'field';
  }
}
function move(event: PointerEvent) {
  if (!enabled || event.pointerType !== 'mouse' || document.hidden) {
    if (state.active) deactivate();
    return;
  }
  const now = performance.now();
  const speed = state.active
    ? Math.hypot(event.clientX - state.x, event.clientY - state.y) /
      Math.max(8, now - lastMove)
    : 0;
  state.x = event.clientX;
  state.y = event.clientY;
  state.active = true;
  inspectTarget(event.target);
  lastMove = now;
  aimRadius(radiusForSpeed(speed), now);
  // Coordinates are written during the event, never interpolated from an old point.
  sampleRadius(now);
  publish();
  if (!frame && (state.radius !== targetRadius || targetRadius !== BASE_RADIUS))
    frame = requestAnimationFrame(animate);
}
function syncPreference() {
  enabled =
    Boolean(fine?.matches) &&
    !reduced?.matches &&
    document.documentElement.dataset.reducedMotion !== 'reduce';
  if (!enabled) deactivate();
}
function visibility() {
  if (document.hidden) deactivate();
}
function outside(event: PointerEvent) {
  if (!event.relatedTarget) deactivate();
}
function refreshAnchor() {
  if (!state.active) return;
  inspectTarget(
    document.elementFromPoint?.(state.x, state.y) || null,
  );
  publish();
}
function connect() {
  fine = window.matchMedia?.('(hover: hover) and (pointer: fine)') || null;
  reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)') || null;
  fine?.addEventListener('change', syncPreference);
  reduced?.addEventListener('change', syncPreference);
  preferenceObserver = new MutationObserver(syncPreference);
  preferenceObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-reduced-motion'],
  });
  window.addEventListener('pointermove', move, {
    capture: true,
    passive: true,
  });
  window.addEventListener('pointerout', outside);
  window.addEventListener('pointercancel', deactivate);
  window.addEventListener('blur', deactivate);
  window.addEventListener('scroll', refreshAnchor, {
    capture: true,
    passive: true,
  });
  window.addEventListener('resize', refreshAnchor, { passive: true });
  document.documentElement.addEventListener('pointerleave', deactivate);
  document.addEventListener('visibilitychange', visibility);
  syncPreference();
  publish();
}
function disconnect() {
  fine?.removeEventListener('change', syncPreference);
  reduced?.removeEventListener('change', syncPreference);
  preferenceObserver?.disconnect();
  fine = reduced = null;
  preferenceObserver = null;
  window.removeEventListener('pointermove', move, true);
  window.removeEventListener('pointerout', outside);
  window.removeEventListener('pointercancel', deactivate);
  window.removeEventListener('blur', deactivate);
  window.removeEventListener('scroll', refreshAnchor, true);
  window.removeEventListener('resize', refreshAnchor);
  document.documentElement.removeEventListener('pointerleave', deactivate);
  document.removeEventListener('visibilitychange', visibility);
  deactivate();
  enabled = false;
  for (const property of properties)
    document.documentElement.style.removeProperty(property);
}

/** One pointer stream and radius animation shared by the global and local lenses. */
export function useMarketPointerReveal(listener: Listener) {
  onMounted(() => {
    listeners.add(listener);
    if (listeners.size === 1) connect();
    else listener(state);
  });
  onBeforeUnmount(() => {
    listeners.delete(listener);
    if (!listeners.size) disconnect();
  });
}
