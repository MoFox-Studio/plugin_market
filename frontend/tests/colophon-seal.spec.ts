import { describe, expect, test } from 'vitest';
import { mount } from '@vue/test-utils';
import ColophonSeal from '@/components/ColophonSeal.vue';
import { impressions } from '@/composables/rareImpressions';

describe('刊记印章', () => {
  test('默认呈现静态藏印图版，不注册鼠标跟随揭示', () => {
    const wrapper = mount(ColophonSeal, {
      props: { print: impressions[0] },
      global: { stubs: { ImpressionArt: true } },
    });

    expect(wrapper.find('.seal-window').exists()).toBe(true);
    expect(wrapper.find('.seal-art').exists()).toBe(true);
    expect(wrapper.find('.blank-imprint').exists()).toBe(false);
    expect(wrapper.find('.is-revealing').exists()).toBe(false);
    wrapper.unmount();
  });
});
