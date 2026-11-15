import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { mount, type VueWrapper } from '@vue/test-utils';
import { defineComponent, h } from 'vue';

const mounted = new Set<VueWrapper>();

beforeEach(() => {
  vi.resetModules();
});

afterEach(() => {
  for (const wrapper of mounted) wrapper.unmount();
  mounted.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  document.documentElement.removeAttribute('style');
});

function setViewport(width: number, height: number, scroll: number) {
  vi.stubGlobal('innerWidth', width);
  vi.stubGlobal('innerHeight', height);
  vi.stubGlobal('scrollY', scroll);
}

async function surveyHarness() {
  setViewport(1440, 900, 37);
  const frames = new Map<number, FrameRequestCallback>();
  let nextFrame = 0;
  const requestFrame = vi.fn((callback: FrameRequestCallback) => {
    frames.set(++nextFrame, callback);
    return nextFrame;
  });
  const cancelFrame = vi.fn((id: number) => { frames.delete(id); });
  vi.stubGlobal('requestAnimationFrame', requestFrame);
  vi.stubGlobal('cancelAnimationFrame', cancelFrame);
  const { useSurveyWorld } = await import('@/composables/useSurveyWorld');

  function consumer() {
    const listener = vi.fn();
    let world!: ReturnType<typeof useSurveyWorld>;
    const wrapper = mount(defineComponent({
      setup() {
        world = useSurveyWorld(listener);
        return () => h('div');
      },
    }));
    mounted.add(wrapper);
    listener.mockClear();
    return {
      world, listener,
      unmount() {
        wrapper.unmount();
        mounted.delete(wrapper);
      },
    };
  }

  function flushFrame() {
    const callbacks = [...frames.values()];
    frames.clear();
    callbacks.forEach(callback => callback(16));
  }

  return { consumer, frames, flushFrame, requestFrame, cancelFrame };
}

// Compatibility oracle: the projection and CSS translations used by HEAD before
// scroll handling moved into rAF. Keep the original constants and operation order.
function legacyProjection(width: number, height: number, scrollY: number) {
  const scroll = Math.max(0, scrollY);
  const scale = Math.max(0.74, width / 1600);
  const first = Math.max(0, Math.floor(scroll / (640 * scale)) - 1);
  const count = Math.ceil(height / (640 * scale)) + 3;
  return {
    scale, first, count,
    x: (width - 1600 * scale) * 0.74,
    y: first * 640 * scale - scroll,
  };
}

const projectionCases = [
  { width: 390, height: 844 },
  { width: 1184, height: 640 },
  { width: 1440, height: 900 },
  { width: 2560, height: 2160 },
].flatMap(viewport => [-0.25, 0, 0.999, 1, 2, 6.75].map(sheet => ({
  ...viewport,
  scroll: sheet * 640 * Math.max(0.74, viewport.width / 1600),
})));

describe('survey camera scheduling and geometry', () => {
  test('a scroll burst reads the latest position once in a single animation frame', async () => {
    const { consumer, frames, flushFrame, requestFrame } = await surveyHarness();
    const { listener } = consumer();
    for (let scroll = 100; scroll < 200; scroll++) {
      vi.stubGlobal('scrollY', scroll);
      window.dispatchEvent(new Event('scroll'));
    }

    expect(requestFrame).toHaveBeenCalledOnce();
    expect(frames.size).toBe(1);
    expect(listener).not.toHaveBeenCalled();
    flushFrame();
    expect(listener).toHaveBeenCalledExactlyOnceWith({ x: 0, y: -199 });
    expect(frames.size).toBe(0);

    vi.stubGlobal('scrollY', 205);
    window.dispatchEvent(new Event('scroll'));
    expect(requestFrame).toHaveBeenCalledTimes(2);
    flushFrame();
    expect(listener).toHaveBeenCalledTimes(2);
    expect(listener.mock.lastCall?.[0]).toEqual({ x: 0, y: -205 });
  });

  test.each(projectionCases)('preserves HEAD projection at $width × $height, scroll $scroll', async ({ width, height, scroll }) => {
    const { consumer, flushFrame, frames } = await surveyHarness();
    const { world, listener } = consumer();
    setViewport(width, height, scroll);
    window.dispatchEvent(new Event('resize'));
    window.dispatchEvent(new Event('scroll'));
    window.dispatchEvent(new Event('pageshow'));
    expect(frames.size).toBe(1);
    expect(listener).not.toHaveBeenCalled();
    flushFrame();

    const expected = legacyProjection(width, height, scroll);
    expect(listener).toHaveBeenCalledExactlyOnceWith({ x: expected.x, y: expected.y });
    expect(world.camera.value).toEqual({
      scale: expected.scale, first: expected.first, count: expected.count, width, height,
    });
    expect(world.sheets.value).toEqual(Array.from({ length: expected.count }, (_, index) => expected.first + index));
    expect(world.viewBox.value).toBe(`0 0 1600 ${640 * expected.count}`);
    expect(world.dimensions.value).toEqual({
      width: 1600 * expected.scale + 'px',
      height: 640 * expected.count * expected.scale + 'px',
    });
  });

  test('mounting, moving, resizing and unmounting leave root styles untouched', async () => {
    const { consumer, flushFrame } = await surveyHarness();
    const rootStyle = document.documentElement.style;
    rootStyle.setProperty('--existing-theme-value', 'unchanged');
    const before = document.documentElement.getAttribute('style');
    const setProperty = vi.spyOn(rootStyle, 'setProperty');
    const removeProperty = vi.spyOn(rootStyle, 'removeProperty');
    const client = consumer();

    setViewport(390, 844, 2300);
    window.dispatchEvent(new Event('scroll'));
    window.dispatchEvent(new Event('resize'));
    flushFrame();
    client.unmount();

    expect(setProperty).not.toHaveBeenCalled();
    expect(removeProperty).not.toHaveBeenCalled();
    expect(document.documentElement.getAttribute('style')).toBe(before);
  });

  test('consumers share event listeners and only the last unmount cancels pending work', async () => {
    const { consumer, frames, flushFrame, requestFrame, cancelFrame } = await surveyHarness();
    const addListener = vi.spyOn(window, 'addEventListener');
    const removeListener = vi.spyOn(window, 'removeEventListener');
    const first = consumer();
    const second = consumer();
    for (const event of ['scroll', 'resize', 'pageshow']) {
      expect(addListener.mock.calls.filter(([name]) => name === event)).toHaveLength(1);
    }
    expect(first.world.camera).toBe(second.world.camera);

    vi.stubGlobal('scrollY', 800);
    window.dispatchEvent(new Event('scroll'));
    first.unmount();
    expect(removeListener).not.toHaveBeenCalled();
    expect(cancelFrame).not.toHaveBeenCalled();
    expect(frames.size).toBe(1);
    flushFrame();
    expect(first.listener).not.toHaveBeenCalled();
    expect(second.listener).toHaveBeenCalledExactlyOnceWith({ x: 0, y: -800 });

    vi.stubGlobal('scrollY', 1700);
    window.dispatchEvent(new Event('scroll'));
    const pendingId = [...frames.keys()][0];
    second.unmount();
    expect(cancelFrame).toHaveBeenCalledExactlyOnceWith(pendingId);
    expect(frames.size).toBe(0);
    for (const event of ['scroll', 'resize', 'pageshow']) {
      const added = addListener.mock.calls.filter(([name]) => name === event);
      const removed = removeListener.mock.calls.filter(([name]) => name === event);
      expect(removed).toHaveLength(1);
      expect(removed[0][1]).toBe(added[0][1]);
    }
    const requestsBeforeUnmountedEvents = requestFrame.mock.calls.length;
    window.dispatchEvent(new Event('scroll'));
    window.dispatchEvent(new Event('resize'));
    window.dispatchEvent(new Event('pageshow'));
    expect(requestFrame).toHaveBeenCalledTimes(requestsBeforeUnmountedEvents);

    const third = consumer();
    vi.stubGlobal('scrollY', 2000);
    window.dispatchEvent(new Event('scroll'));
    expect(frames.size).toBe(1);
    flushFrame();
    const expected = legacyProjection(1440, 900, 2000);
    expect(third.listener).toHaveBeenCalledExactlyOnceWith({ x: expected.x, y: expected.y });
    for (const event of ['scroll', 'resize', 'pageshow']) {
      expect(addListener.mock.calls.filter(([name]) => name === event)).toHaveLength(2);
    }
  });
});
