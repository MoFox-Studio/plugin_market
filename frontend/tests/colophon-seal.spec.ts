import { afterEach, describe, expect, test, vi } from 'vitest';
import { mount, type VueWrapper } from '@vue/test-utils';
import type { MarketPointerRevealState } from '@/composables/useMarketPointerReveal';
import ColophonSeal from '@/components/ColophonSeal.vue';
import { impressions } from '@/composables/rareImpressions';

const stream = vi.hoisted(() => ({
  listener: undefined as ((pointer: Readonly<MarketPointerRevealState>) => void) | undefined,
}));
vi.mock('@/composables/useMarketPointerReveal', () => ({
  useMarketPointerReveal: (listener: typeof stream.listener) => { stream.listener = listener; },
}));

let wrapper: VueWrapper | undefined;
afterEach(() => {
  wrapper?.unmount();
  stream.listener = undefined;
  vi.restoreAllMocks();
});

describe('colophon pointer lens', () => {
  test('keeps both original radius extremes local to the seal and clears reveal on exit', () => {
    const rootStyles = document.documentElement.getAttribute('style');
    wrapper = mount(ColophonSeal, {
      props: { print: impressions[0] },
      global: { stubs: { ImpressionArt: true } },
    });
    const field = wrapper.find<HTMLElement>('.seal-window');
    vi.spyOn(field.element, 'getBoundingClientRect').mockReturnValue({
      x: 100, y: 200, left: 100, top: 200, right: 340, bottom: 460,
      width: 240, height: 260, toJSON: () => ({}),
    });
    const pointer: MarketPointerRevealState = {
      x: 160, y: 280, radius: 40, active: true, local: true, surface: 'control',
    };
    for (const radius of [40, 110]) {
      stream.listener!({ ...pointer, radius });
      expect(field.classes()).toContain('is-revealing');
      expect(field.element.style.getPropertyValue('--seal-radius')).toBe(`${radius}px`);
      expect(field.element.style.getPropertyValue('--seal-x')).toBe('60px');
      expect(field.element.style.getPropertyValue('--seal-y')).toBe('80px');
      expect(document.documentElement.getAttribute('style')).toBe(rootStyles);
    }
    stream.listener!({ ...pointer, active: false, local: false });
    expect(field.classes()).not.toContain('is-revealing');
  });
});
