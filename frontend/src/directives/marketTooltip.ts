import type { App, Directive, DirectiveBinding } from 'vue';
import '@/assets/tooltip.css';

type Placement = 'top' | 'bottom' | 'left' | 'right';
export type MarketTooltipValue =
  | string
  | number
  | false
  | null
  | undefined
  | {
      text: string;
      placement?: Placement;
      delay?: number;
    };
interface TooltipState {
  element: HTMLElement;
  text: string;
  placement: Placement;
  delay: number;
  hovered: boolean;
  focused: boolean;
  dismissed: boolean;
  showTimer: ReturnType<typeof setTimeout> | null;
  hideTimer: ReturnType<typeof setTimeout> | null;
  descriptionId: string | null;
  removeListeners: () => void;
}
const states = new Map<HTMLElement, TooltipState>();
let active: TooltipState | null = null;
let bubble: HTMLElement | null = null;
let bubbleHovered = false;
let frame = 0;
let sequence = 0;
let touchInteraction = false;
const GAP = 10;
const MARGIN = 8;
const placements: Placement[] = ['top', 'bottom', 'left', 'right'];

function configure(
  state: TooltipState,
  binding: DirectiveBinding<MarketTooltipValue>,
) {
  const value = binding.value;
  const object = value && typeof value === 'object' ? value : null;
  state.text = String(
    object ? object.text : value === false || value == null ? '' : value,
  ).trim();
  const requested = object?.placement || binding.arg;
  state.placement = placements.includes(requested as Placement)
    ? (requested as Placement)
    : 'top';
  state.delay = Math.max(0, object?.delay ?? 420);
  state.element.removeAttribute('title');
}
function clearTimers(state: TooltipState) {
  if (state.showTimer !== null) clearTimeout(state.showTimer);
  if (state.hideTimer !== null) clearTimeout(state.hideTimer);
  state.showTimer = state.hideTimer = null;
}
function removeDescription(state: TooltipState) {
  if (!state.descriptionId) return;
  const remaining = (state.element.getAttribute('aria-describedby') || '')
    .split(/\s+/)
    .filter((id) => id && id !== state.descriptionId);
  if (remaining.length)
    state.element.setAttribute('aria-describedby', remaining.join(' '));
  else state.element.removeAttribute('aria-describedby');
  state.descriptionId = null;
}
function hide(state: TooltipState) {
  clearTimers(state);
  removeDescription(state);
  if (active !== state) return;
  cancelAnimationFrame(frame);
  frame = 0;
  bubble?.remove();
  bubble = null;
  active = null;
  bubbleHovered = false;
}
function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(value, Math.max(min, max)));
}
function positionBubble() {
  if (!active || !bubble) return;
  const element = active.element;
  const rect = element.getBoundingClientRect();
  if (!element.isConnected || (rect.width === 0 && rect.height === 0)) {
    hide(active);
    return;
  }
  const viewport = window.visualViewport;
  const leftEdge = (viewport?.offsetLeft || 0) + MARGIN;
  const topEdge = (viewport?.offsetTop || 0) + MARGIN;
  const rightEdge =
    leftEdge + (viewport?.width || window.innerWidth) - MARGIN * 2;
  const bottomEdge =
    topEdge + (viewport?.height || window.innerHeight) - MARGIN * 2;
  if (
    rect.bottom < topEdge ||
    rect.top > bottomEdge ||
    rect.right < leftEdge ||
    rect.left > rightEdge
  ) {
    hide(active);
    return;
  }
  bubble.style.maxWidth =
    Math.max(1, Math.min(280, rightEdge - leftEdge)) + 'px';
  const box = bubble.getBoundingClientRect();
  let placement = active.placement;
  if (placement === 'top' && rect.top - box.height - GAP < topEdge)
    placement = 'bottom';
  else if (
    placement === 'bottom' &&
    rect.bottom + box.height + GAP > bottomEdge
  )
    placement = 'top';
  else if (placement === 'left' && rect.left - box.width - GAP < leftEdge)
    placement = 'right';
  else if (placement === 'right' && rect.right + box.width + GAP > rightEdge)
    placement = 'left';
  let left = rect.left + (rect.width - box.width) / 2;
  let top =
    placement === 'top' ? rect.top - box.height - GAP : rect.bottom + GAP;
  if (placement === 'left' || placement === 'right') {
    left =
      placement === 'left' ? rect.left - box.width - GAP : rect.right + GAP;
    top = rect.top + (rect.height - box.height) / 2;
  }
  left = clamp(left, leftEdge, rightEdge - box.width);
  top = clamp(top, topEdge, bottomEdge - box.height);
  bubble.style.left = Math.round(left) + 'px';
  bubble.style.top = Math.round(top) + 'px';
  bubble.style.setProperty(
    '--tooltip-arrow-x',
    clamp(rect.left + rect.width / 2 - left, 9, box.width - 9) + 'px',
  );
  bubble.style.setProperty(
    '--tooltip-arrow-y',
    clamp(rect.top + rect.height / 2 - top, 9, box.height - 9) + 'px',
  );
  bubble.dataset.placement = placement;
}
function followAnchor() {
  positionBubble();
  if (active && bubble) frame = requestAnimationFrame(followAnchor);
}
function scheduleHide(state: TooltipState) {
  if (state.showTimer !== null) clearTimeout(state.showTimer);
  state.showTimer = null;
  if (state.hovered || state.focused || (active === state && bubbleHovered))
    return;
  if (state.hideTimer !== null) clearTimeout(state.hideTimer);
  // Allows a pointer to cross the small gap and read the tooltip itself.
  state.hideTimer = setTimeout(() => hide(state), 120);
}
function show(state: TooltipState) {
  clearTimers(state);
  if (
    !state.text ||
    state.dismissed ||
    !state.element.isConnected ||
    document.hidden ||
    (!state.hovered && !state.focused)
  )
    return;
  if (active && active !== state) hide(active);
  if (active === state && bubble) {
    bubble.textContent = state.text;
    positionBubble();
    return;
  }
  active = state;
  bubble = document.createElement('div');
  bubble.className = 'market-tooltip';
  bubble.id = `market-tooltip-${++sequence}`;
  bubble.setAttribute('role', 'tooltip');
  bubble.textContent = state.text;
  bubble.addEventListener('pointerenter', (event) => {
    if (event.pointerType === 'touch') return;
    bubbleHovered = true;
    if (state.hideTimer !== null) clearTimeout(state.hideTimer);
    state.hideTimer = null;
  });
  bubble.addEventListener('pointerleave', () => {
    bubbleHovered = false;
    scheduleHide(state);
  });
  const host = state.element.closest('dialog[open]') || document.body;
  host.appendChild(bubble);
  state.descriptionId = bubble.id;
  const descriptions = new Set(
    (state.element.getAttribute('aria-describedby') || '')
      .split(/\s+/)
      .filter(Boolean),
  );
  descriptions.add(bubble.id);
  state.element.setAttribute('aria-describedby', [...descriptions].join(' '));
  followAnchor();
}
function scheduleShow(state: TooltipState, delay: number) {
  clearTimers(state);
  if (!state.text || state.dismissed) return;
  if (active === state) {
    positionBubble();
    return;
  }
  state.showTimer = setTimeout(() => show(state), delay);
}
function onKeydown(event: KeyboardEvent) {
  touchInteraction = false;
  if (event.key !== 'Escape') return;
  const visible = Boolean(active);
  for (const state of states.values()) {
    if (
      state.hovered ||
      state.focused ||
      state.showTimer !== null ||
      state === active
    ) {
      state.dismissed = true;
      hide(state);
    }
  }
  if (visible) {
    event.preventDefault();
    event.stopImmediatePropagation();
  }
}
function onPointerDown(event: PointerEvent) {
  touchInteraction = event.pointerType === 'touch';
  if (!touchInteraction) return;
  for (const state of states.values()) {
    state.hovered = false;
    state.focused = false;
    hide(state);
  }
}
function onVisibilityChange() {
  if (document.hidden) for (const state of states.values()) hide(state);
}
function installListeners() {
  document.addEventListener('keydown', onKeydown, true);
  document.addEventListener('pointerdown', onPointerDown, true);
  document.addEventListener('visibilitychange', onVisibilityChange);
}
function removeGlobalListeners() {
  document.removeEventListener('keydown', onKeydown, true);
  document.removeEventListener('pointerdown', onPointerDown, true);
  document.removeEventListener('visibilitychange', onVisibilityChange);
  touchInteraction = false;
}
export const marketTooltip: Directive<HTMLElement, MarketTooltipValue> = {
  mounted(element, binding) {
    const state: TooltipState = {
      element,
      text: '',
      placement: 'top',
      delay: 420,
      hovered: false,
      focused: false,
      dismissed: false,
      showTimer: null,
      hideTimer: null,
      descriptionId: null,
      removeListeners: () => {},
    };
    configure(state, binding);
    const enter = (event: PointerEvent) => {
      if (event.pointerType === 'touch') return;
      state.hovered = true;
      state.dismissed = false;
      scheduleShow(state, state.delay);
    };
    const leave = () => {
      state.hovered = false;
      scheduleHide(state);
    };
    const focus = () => {
      if (touchInteraction) return;
      state.focused = true;
      state.dismissed = false;
      scheduleShow(state, Math.min(state.delay, 140));
    };
    const blur = (event: FocusEvent) => {
      if (
        event.relatedTarget instanceof Node &&
        element.contains(event.relatedTarget)
      )
        return;
      state.focused = false;
      scheduleHide(state);
    };
    element.addEventListener('pointerenter', enter);
    element.addEventListener('pointerleave', leave);
    element.addEventListener('focusin', focus);
    element.addEventListener('focusout', blur);
    state.removeListeners = () => {
      element.removeEventListener('pointerenter', enter);
      element.removeEventListener('pointerleave', leave);
      element.removeEventListener('focusin', focus);
      element.removeEventListener('focusout', blur);
    };
    if (!states.size) installListeners();
    states.set(element, state);
  },
  updated(element, binding) {
    const state = states.get(element);
    if (!state) return;
    configure(state, binding);
    if (!state.text) hide(state);
    else if (active === state && bubble) {
      bubble.textContent = state.text;
      positionBubble();
    }
  },
  beforeUnmount(element) {
    const state = states.get(element);
    if (!state) return;
    hide(state);
    state.removeListeners();
    states.delete(element);
    if (!states.size) removeGlobalListeners();
  },
};
export function installMarketTooltip(app: App) {
  app.directive('market-tooltip', marketTooltip);
}
