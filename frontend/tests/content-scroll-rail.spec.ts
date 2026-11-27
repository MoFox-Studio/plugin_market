import { afterEach, describe, expect, test, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createMemoryHistory, createRouter } from 'vue-router';
import { defineComponent, h } from 'vue';
import ContentScrollRail from '@/components/ContentScrollRail.vue';

const railItems = [
  { id: 'rail-section-one', label: '第一段' },
  { id: 'rail-section-two', label: '第二段' },
];

const TestSurface = defineComponent({
  setup() {
    return () => h('main', [
      h('section', { id: 'rail-section-one', tabindex: -1 }, '第一段内容'),
      h('section', { id: 'rail-section-two', tabindex: -1 }, '第二段内容'),
      h(ContentScrollRail, { items: railItems, ariaLabel: '测试分段导航' }),
    ]);
  },
});

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: defineComponent({ render: () => h('div') }) }],
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  document.body.innerHTML = '';
});

describe('内容滚动侧栏', () => {
  test('呈现有名称的分段链接并标记初始活动目标', async () => {
    const router = makeRouter();
    await router.push('/');
    const wrapper = mount(TestSurface, {
      attachTo: document.body,
      global: { plugins: [router] },
    });
    await flushPromises();

    expect(wrapper.get('nav').attributes('aria-label')).toBe('测试分段导航');
    expect(wrapper.findAll('.content-scroll-rail__item').map((link) => link.text())).toEqual([
      '01第一段',
      '02第二段',
    ]);
    expect(wrapper.findAll('.content-scroll-rail__item small')).toHaveLength(0);
    expect(wrapper.findAll('a[aria-current="location"]')).toHaveLength(1);
    expect(wrapper.get('#rail-section-one').attributes('tabindex')).toBe('-1');
    wrapper.unmount();
  });

  test('选择段落更新片段路由、滚动并将焦点交给目标区域', async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoView,
    });

    const router = makeRouter();
    await router.push('/?q=mofox');
    const wrapper = mount(TestSurface, {
      attachTo: document.body,
      global: { plugins: [router] },
    });
    await flushPromises();
    await wrapper.get('a[href="#rail-section-two"]').trigger('click');
    await flushPromises();

    expect(router.currentRoute.value.hash).toBe('#rail-section-two');
    expect(router.currentRoute.value.query).toEqual({ q: 'mofox' });
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });
    expect(wrapper.get('a[aria-current="location"]').attributes('href')).toBe('#rail-section-two');
    expect(document.activeElement).toBe(wrapper.get('#rail-section-two').element);
    wrapper.unmount();
  });

  test('鼠标移动不会驱动分段项位移', async () => {
    const router = makeRouter();
    await router.push('/');
    const wrapper = mount(TestSurface, {
      attachTo: document.body,
      global: { plugins: [router] },
    });
    await flushPromises();

    await wrapper.get('.content-scroll-rail__list').trigger('pointermove', { clientY: 36 });
    expect(
      wrapper.findAll('.content-scroll-rail__item').every((link) => link.element.getAttribute('style') === null),
    ).toBe(true);
    wrapper.unmount();
  });
});
