import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { mount, type VueWrapper } from '@vue/test-utils';
import { defineComponent, nextTick } from 'vue';

let wrapper: VueWrapper | undefined;

beforeEach(() => {
  vi.resetModules();
  document.documentElement.removeAttribute('data-reduced-motion');
  document.documentElement.removeAttribute('style');
  document.body.innerHTML = '';
});
afterEach(() => {
  wrapper?.unmount();
  wrapper = undefined;
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  delete window.__mofoxBoot;
});

describe('the complete intro stays available', () => {
  test('the original intro plays before revealing a ready route', async () => {
    vi.useFakeTimers();
    document.body.innerHTML = '<div id="boot-screen"></div><div id="app" inert></div>';
    const stopWatch = vi.fn();
    window.__mofoxBoot = { startedAt: performance.now(), stopWatch, fail: vi.fn() };
    const { finishBoot, booting, BOOT_MINIMUM_MS } = await import('@/composables/useLoadingState');
    finishBoot();
    expect(booting.value).toBe(true);
    await vi.advanceTimersByTimeAsync(BOOT_MINIMUM_MS);
    expect(document.getElementById('boot-screen')?.dataset.phase).toBe('leaving');
    await vi.advanceTimersByTimeAsync(200);
    expect(booting.value).toBe(false);
    expect(document.getElementById('boot-screen')).toBeNull();
    expect(document.getElementById('app')?.hasAttribute('inert')).toBe(false);
    expect(stopWatch).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
  });

  test('explicitly skipping the intro enables a ready app immediately', async () => {
    vi.useFakeTimers();
    document.body.innerHTML = '<div id="boot-screen"></div><div id="app" inert></div>';
    window.__mofoxBoot = { startedAt: performance.now(), stopWatch: vi.fn(), fail: vi.fn() };
    const { finishBoot, booting } = await import('@/composables/useLoadingState');
    finishBoot();
    window.dispatchEvent(new Event('mofox:skip-intro'));
    expect(booting.value).toBe(false);
    expect(document.getElementById('app')?.hasAttribute('inert')).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });

  test('startup failure keeps the retry screen available', async () => {
    document.body.innerHTML = '<div id="boot-screen" data-phase="failed"></div><div id="app" inert></div>';
    const { finishBoot, booting } = await import('@/composables/useLoadingState');
    finishBoot();
    expect(booting.value).toBe(true);
    expect(document.getElementById('boot-screen')).not.toBeNull();
    expect(document.getElementById('app')?.hasAttribute('inert')).toBe(true);
  });
});

async function pointerHarness(fine = true, reduced = false) {
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
  vi.stubGlobal('matchMedia', vi.fn((query: string) => ({
    matches: query.includes('pointer: fine') ? fine : reduced,
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
  })));
  let now = 0;
  vi.spyOn(performance, 'now').mockImplementation(() => now);
  const frames = new Map<number, FrameRequestCallback>();
  let id = 0;
  vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => {
    frames.set(++id, callback);
    return id;
  }));
  vi.stubGlobal('cancelAnimationFrame', vi.fn((key: number) => frames.delete(key)));
  const listener = vi.fn();
  const { useMarketPointerReveal } = await import('@/composables/useMarketPointerReveal');
  wrapper = mount(defineComponent({
    setup() { useMarketPointerReveal(listener); },
    template: '<div data-pointer-reveal-local></div>',
  }), { attachTo: document.body });
  listener.mockClear();
  function move(x: number) {
    const event = new MouseEvent('pointermove', { clientX: x, clientY: 20, bubbles: true });
    Object.defineProperty(event, 'pointerType', { value: 'mouse' });
    wrapper!.element.dispatchEvent(event);
  }
  function flushFrame(elapsed = 16) {
    now += elapsed;
    const queued = [...frames.values()];
    frames.clear();
    queued.forEach(callback => callback(now));
  }
  return { frames, listener, move, flushFrame };
}

describe('pointer decoration stays bounded', () => {
  test('bursts use the latest coordinate once per frame without changing root styles', async () => {
    const { frames, listener, move, flushFrame } = await pointerHarness();
    for (let x = 0; x < 50; x++) move(x);
    expect(listener).not.toHaveBeenCalled();
    expect(frames.size).toBe(1);
    flushFrame();
    expect(listener).toHaveBeenCalledOnce();
    expect(listener.mock.calls[0][0]).toMatchObject({ x: 49, y: 20, active: true, local: true });
    for (let i = 0; i < 30; i++) flushFrame();
    expect(listener.mock.lastCall?.[0].radius).toBe(110);
    expect(frames.size).toBe(0);
    expect(document.documentElement.getAttribute('style')).toBeNull();
    window.dispatchEvent(new Event('scroll'));
    expect(frames.size).toBe(1);
    flushFrame();
    expect(listener.mock.lastCall?.[0].active).toBe(true);
    window.dispatchEvent(new Event('blur'));
    expect(listener.mock.lastCall?.[0].active).toBe(false);
    expect(frames.size).toBe(0);
  });

  test.each([[false, false], [true, true]])('does not animate coarse or reduced-motion input (%s, %s)', async (fine, reduced) => {
    const { frames, listener, move } = await pointerHarness(fine, reduced);
    move(20);
    expect(frames.size).toBe(0);
    expect(listener).not.toHaveBeenCalled();
  });

  test('a motion preference change cancels pending work', async () => {
    const { frames, listener, move } = await pointerHarness();
    move(20);
    expect(frames.size).toBe(1);
    document.documentElement.dataset.reducedMotion = 'reduce';
    await nextTick();
    expect(frames.size).toBe(0);
    expect(listener.mock.lastCall?.[0].active).toBe(false);
  });
});
