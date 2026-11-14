import { nextTick, watch } from 'vue';
import type { RouteLocationNormalized } from 'vue-router';
import { navigationEpoch, scrollRestorationBusy } from './useLoadingState';

export const SCROLL_RESTORATION_TIMEOUT = 12500;
const DEFAULT_HEADER_OFFSET = 88;
interface SavedPosition {
  left: number;
  top: number;
}
interface Restoration {
  hash: string;
  savedPosition: SavedPosition | null;
  keepPosition?: boolean;
  epoch: number;
  isCurrent: () => boolean;
}

let cancelPending: (() => void) | null = null;

const chapterTabs = new Set(['#overview', '#readme', '#versions', '#comments']);

export function keepsReadingPosition(to: RouteLocationNormalized, from: RouteLocationNormalized): boolean {
  if (!from.matched.length || to.path !== from.path) return false;
  if (!to.hash) return true;
  if ((to.name === 'plugin' || to.name === 'skill') && chapterTabs.has(to.hash)) return true;
  // Updating a query on an anchored page is not a new request to visit that anchor.
  return to.hash === from.hash && to.fullPath !== from.fullPath;
}

function hashTarget(hash: string): HTMLElement | null {
  let id = hash.slice(1);
  try {
    id = decodeURIComponent(id);
  } catch {
    /* Keep a literal malformed ID. */
  }
  return document.getElementById(id);
}

function documentSize() {
  const root = document.documentElement;
  return {
    height: Math.max(root.scrollHeight, document.body?.scrollHeight || 0),
    width: Math.max(root.scrollWidth, document.body?.scrollWidth || 0),
    viewportHeight: root.clientHeight || window.innerHeight,
    viewportWidth: root.clientWidth || window.innerWidth,
  };
}

function anchorOffset(target: HTMLElement): number {
  const declared = Number.parseFloat(getComputedStyle(target).scrollMarginTop);
  if (Number.isFinite(declared) && declared > 0) return declared;
  const height = (selector: string) =>
    document.querySelector<HTMLElement>(selector)?.getBoundingClientRect()
      .height || 0;
  return Math.max(
    DEFAULT_HEADER_OFFSET,
    height('.market-header') + height('.dossier-navigation') + 16,
  );
}

/** Restore once, after this navigation's content can actually contain the target.
 *
 * We apply the scroll ourselves and return false to Vue Router. This keeps the
 * final navigation check and scrolling in one synchronous operation, so a late
 * router promise cannot apply an old position after another navigation starts.
 */
export function restoreRouteScroll(options: Restoration): Promise<false> {
  cancelPending?.();
  const current = () =>
    options.epoch === navigationEpoch.value && options.isCurrent();
  if (!current()) return Promise.resolve(false);
  if (!options.savedPosition && options.keepPosition) return Promise.resolve(false);
  if (!options.savedPosition && !options.hash) {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
    return Promise.resolve(false);
  }

  return new Promise<false>((resolve) => {
    let finished = false;
    let frame = 0;
    let lastLayout = '';
    let stableFrames = 0;
    let stopWatching = () => {};
    const cancel = () => finish();

    function finish(position?: SavedPosition) {
      if (finished) return;
      finished = true;
      clearTimeout(deadline);
      cancelAnimationFrame(frame);
      stopWatching();
      window.removeEventListener('wheel', cancel, true);
      window.removeEventListener('touchmove', cancel, true);
      window.removeEventListener('pointerdown', cancel, true);
      window.removeEventListener('keydown', onKey, true);
      if (cancelPending === cancel) cancelPending = null;
      if (position && current())
        window.scrollTo({ ...position, behavior: 'instant' });
      resolve(false);
    }

    function onKey(event: KeyboardEvent) {
      if (event.defaultPrevented) return;
      const target = event.target instanceof Element ? event.target : null;
      if (target?.closest('input, textarea, select, [contenteditable="true"]'))
        return;
      if (
        [
          'ArrowUp',
          'ArrowDown',
          'ArrowLeft',
          'ArrowRight',
          'PageUp',
          'PageDown',
          'Home',
          'End',
          ' ',
        ].includes(event.key)
      )
        cancel();
    }

    function destination(allowClamp = false): SavedPosition | null {
      const size = documentSize();
      const maxTop = Math.max(0, size.height - size.viewportHeight);
      const maxLeft = Math.max(0, size.width - size.viewportWidth);
      if (options.savedPosition) {
        const saved = options.savedPosition;
        if (!allowClamp && (saved.top > maxTop + 1 || saved.left > maxLeft + 1))
          return null;
        return {
          top: Math.min(saved.top, maxTop),
          left: Math.min(saved.left, maxLeft),
        };
      }
      const target = hashTarget(options.hash);
      // A hash in a still-hidden tab is not ready to be scrolled into view.
      if (!target || !target.getClientRects().length) return null;
      return {
        top: Math.max(
          0,
          target.getBoundingClientRect().top +
            window.scrollY -
            anchorOffset(target),
        ),
        left: 0,
      };
    }

    function check() {
      if (finished) return;
      if (!current()) {
        finish();
        return;
      }
      const position = scrollRestorationBusy.value ? null : destination();
      if (position) {
        const size = documentSize();
        const layout = `${size.height}:${size.width}:${position.top}:${position.left}`;
        stableFrames = layout === lastLayout ? stableFrames + 1 : 1;
        lastLayout = layout;
        if (stableFrames >= 2) {
          finish(position);
          return;
        }
      } else {
        stableFrames = 0;
        lastLayout = '';
      }
      frame = requestAnimationFrame(check);
    }

    const deadline = setTimeout(() => {
      // A changed catalogue can be genuinely shorter than its old position.
      // Clamp once only after loading ended; never scroll a pending/erroring task.
      finish(
        current() && !scrollRestorationBusy.value
          ? destination(true) || undefined
          : undefined,
      );
    }, SCROLL_RESTORATION_TIMEOUT);
    cancelPending = cancel;
    stopWatching = watch(navigationEpoch, cancel, { flush: 'sync' });
    window.addEventListener('wheel', cancel, { capture: true, passive: true });
    window.addEventListener('touchmove', cancel, {
      capture: true,
      passive: true,
    });
    window.addEventListener('pointerdown', cancel, {
      capture: true,
      passive: true,
    });
    window.addEventListener('keydown', onKey, true);
    // API completion precedes its consumer's reactive updates. The DOM tick and
    // two animation frames also cover those queued renders and layout changes.
    void nextTick().then(() => {
      if (!finished) frame = requestAnimationFrame(check);
    });
  });
}
