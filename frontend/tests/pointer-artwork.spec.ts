import { afterEach, describe, expect, test, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { defineComponent, nextTick } from 'vue';
import GlobalPointerReveal from '@/components/GlobalPointerReveal.vue';

vi.mock('@/composables/useMarketPointerReveal', () => ({
  useMarketPointerReveal: vi.fn(),
}));

const Artwork = defineComponent({
  name: 'SurveyOverprint',
  setup(_, { expose }) {
    expose({ setLensPosition: vi.fn() });
  },
  template: '<svg data-test="pointer-artwork" />',
});

afterEach(() => {
  vi.unstubAllGlobals();
  document.documentElement.removeAttribute('data-reduced-motion');
});

describe('pointer artwork follows its existing CSS capability boundary', () => {
  test.each([false, true])('mounts only for eligible pointer/motion media (%s)', (matches) => {
    const media = { matches, addEventListener: vi.fn(), removeEventListener: vi.fn() };
    const matchMedia = vi.fn(() => media);
    vi.stubGlobal('matchMedia', matchMedia);
    const wrapper = mount(GlobalPointerReveal, { global: { stubs: { SurveyOverprint: Artwork } } });
    return nextTick().then(() => {
      expect(matchMedia).toHaveBeenCalledWith('(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)');
      expect(wrapper.find('[data-test="pointer-artwork"]').exists()).toBe(matches);
      wrapper.unmount();
      expect(media.removeEventListener).toHaveBeenCalledWith('change', expect.any(Function));
    });
  });

  test('respects an explicit root motion override and restores after it is removed', async () => {
    document.documentElement.dataset.reducedMotion = 'reduce';
    const media = { matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() };
    vi.stubGlobal('matchMedia', vi.fn(() => media));
    const wrapper = mount(GlobalPointerReveal, { global: { stubs: { SurveyOverprint: Artwork } } });
    await nextTick();
    expect(wrapper.find('[data-test="pointer-artwork"]').exists()).toBe(false);
    document.documentElement.dataset.reducedMotion = 'no-preference';
    await nextTick();
    await nextTick();
    expect(wrapper.find('[data-test="pointer-artwork"]').exists()).toBe(true);
    document.documentElement.dataset.reducedMotion = 'reduce';
    await nextTick();
    await nextTick();
    expect(wrapper.find('[data-test="pointer-artwork"]').exists()).toBe(false);
    wrapper.unmount();
  });

  test('restores the same artwork when capabilities change and releases it when disabled', async () => {
    const media = { matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() };
    vi.stubGlobal('matchMedia', vi.fn(() => media));
    const wrapper = mount(GlobalPointerReveal, { global: { stubs: { SurveyOverprint: Artwork } } });
    const changed = media.addEventListener.mock.calls[0][1] as () => void;
    expect(wrapper.find('[data-test="pointer-artwork"]').exists()).toBe(false);
    media.matches = true;
    changed();
    await nextTick();
    expect(wrapper.find('[data-test="pointer-artwork"]').exists()).toBe(true);
    media.matches = false;
    changed();
    await nextTick();
    expect(wrapper.find('[data-test="pointer-artwork"]').exists()).toBe(false);
    wrapper.unmount();
  });
});
