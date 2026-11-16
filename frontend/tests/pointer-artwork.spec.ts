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

describe('指针装饰遵循现有 CSS 能力边界', () => {
  test.each([false, true])('仅在指针与动态效果媒体条件满足时挂载（%s）', (matches) => {
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

  test('遵循根元素上显式覆盖的动态效果设置，并在移除覆盖后恢复', async () => {
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

  test('能力变化时恢复相同装饰，并在禁用时释放', async () => {
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
