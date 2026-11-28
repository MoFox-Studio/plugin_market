import { describe, expect, test } from 'vitest';
import { mount } from '@vue/test-utils';
import CategoryIndex from '@/components/catalog/CategoryIndex.vue';

describe('目录分类索引', () => {
  test('目录筛选项以可换行的中文标签呈现并保留按钮语义', async () => {
    const wrapper = mount(CategoryIndex, {
      props: { categories: ['entertainment', 'tools'] },
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    });

    const entries = wrapper.findAll('.category-entry');
    expect(entries).toHaveLength(3);
    expect(entries.map((entry) => entry.find('.category-entry__label').text())).toEqual([
      '全部',
      'entertainment',
      '工具合集',
    ]);
    expect(entries.every((entry) => entry.element.tagName === 'BUTTON')).toBe(true);
    expect(entries.every((entry) => entry.attributes('type') === 'button')).toBe(true);
    expect(wrapper.find('.category-entry__copy').exists()).toBe(false);
    expect(wrapper.find('.category-entry__number').exists()).toBe(false);
    expect(wrapper.find('.category-entry__arrow').exists()).toBe(false);

    await entries[1].trigger('click');
    expect(wrapper.emitted('update:modelValue')).toEqual([['entertainment']]);
  });

  test('首页发现区继续保留原有图版条目结构', () => {
    const wrapper = mount(CategoryIndex, {
      props: { categories: ['tools'], discovery: true },
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    });

    expect(wrapper.find('.category-index').classes()).toContain('is-discovery');
    expect(wrapper.find('.category-entry__copy').exists()).toBe(true);
    expect(wrapper.find('.category-entry__number').text()).toBe('01');
    expect(wrapper.find('.category-entry__arrow').exists()).toBe(true);
    expect(wrapper.find('.category-entry__label').exists()).toBe(false);
  });
});
