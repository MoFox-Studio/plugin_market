import { afterEach, describe, expect, test, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createPinia } from 'pinia';
import { createMemoryHistory, createRouter, useRoute } from 'vue-router';
import { defineComponent, h } from 'vue';
import type { Plugin } from '@/types';
import AppHeader from '@/components/AppHeader.vue';
import HomeFinder from '@/components/HomeFinder.vue';
import HomeIndex from '@/components/HomeIndex.vue';
import SpotlightFeature from '@/components/SpotlightFeature.vue';

const RouteStub = defineComponent({ render: () => h('main') });
const SiteSurface = defineComponent({
  setup() {
    const route = useRoute();
    return () => h('div', [
      h(AppHeader),
      route.name === 'home' ? h(HomeFinder) : null,
    ]);
  },
});

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: RouteStub },
      { path: '/browse', name: 'market', component: RouteStub },
      { path: '/skills', name: 'skills', component: RouteStub },
      { path: '/plugin/:id', name: 'plugin', component: RouteStub },
    ],
  });
}

function plugin(id: string): Plugin {
  return {
    plugin_id: id,
    display_name: id,
    summary: '用途清楚的社区插件。',
    status: 'published',
    trust_level: 'community',
    owner_id: 'author',
    repository_url: 'https://github.com/MoFox-Studio/sample',
    maintainers: [],
    likes_count: 0,
    downloads_count: 0,
    comments_count: 0,
    rating_avg: 0,
    rating_count: 0,
    updated_at: '2026-01-01T00:00:00Z',
  };
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('首页焦点层级保持原有视觉体系', () => {
  test('首页主搜索不与顶栏重复，进入目录后仍保留全局搜索', async () => {
    const router = makeRouter();
    await router.push('/');
    await router.isReady();
    const wrapper = mount(SiteSurface, {
      global: {
        plugins: [createPinia(), router],
        stubs: {
          AppIcon: true,
          FoxMark: true,
          InboxBell: true,
        },
      },
    });
    await flushPromises();

    expect(wrapper.find('.finder-form[role="search"]').exists()).toBe(true);
    expect(wrapper.find('.header-search').exists()).toBe(false);
    expect(wrapper.findAll('form[role="search"]')).toHaveLength(1);
    expect(wrapper.get('.finder-all').attributes('href')).toBe('/browse');
    expect(wrapper.get('.finder-all').text()).toContain('全部插件');
    expect(wrapper.get('.finder-all-label').exists()).toBe(true);
    expect(wrapper.find('.finder-alternatives').exists()).toBe(false);
    expect(wrapper.find('.finder-skills').exists()).toBe(false);

    await wrapper.get('input[name="q"]').setValue(' 天气 ');
    await wrapper.get('.finder-form').trigger('submit');
    await flushPromises();
    expect(router.currentRoute.value.query).toEqual({ q: '天气' });
    await flushPromises();
    expect(wrapper.find('.home-finder').exists()).toBe(false);
    expect(wrapper.find('.header-search[role="search"]').exists()).toBe(true);
    expect(wrapper.findAll('form[role="search"]')).toHaveLength(1);
    wrapper.unmount();
  });

  test('索引区承载用途与技能入口，不再展示插件速览卡片', async () => {
    const router = makeRouter();
    await router.push('/');
    const wrapper = mount(HomeIndex, {
      props: { categories: ['tools'] },
      global: {
        plugins: [router],
        stubs: {
          AppIcon: true,
          MarketSelect: { template: '<button class="purpose-stub">按用途找插件</button>' },
        },
      },
    });
    expect(wrapper.get('#home-index-title').text()).toBe('浏览插件与技能');
    expect(wrapper.get('.purpose-stub').text()).toBe('按用途找插件');
    expect(wrapper.get('.home-index__skills').attributes('href')).toBe('/skills');
    wrapper.unmount();
  });

  test('精选默认停留且保留原图版；用户仍可手动切换并主动启用自动切换', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('IntersectionObserver', undefined);
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
    const router = makeRouter();
    await router.push('/');
    await router.isReady();
    const items = [plugin('精选插件一'), plugin('精选插件二')];
    const wrapper = mount(SpotlightFeature, {
      props: { items },
      global: {
        plugins: [createPinia(), router],
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
          PluginCard: { template: '<a class="plugin-card-stub"><slot /></a>' },
          SpotlightPlate: { template: '<div class="original-spotlight-plate" />' },
        },
      },
    });
    await flushPromises();

    expect(wrapper.find('.original-spotlight-plate').exists()).toBe(true);
    expect(wrapper.find('h3').text()).toBe('精选插件一');
    const playback = wrapper.get('button[aria-label="自动切换精选"]');
    expect(playback.attributes('aria-pressed')).toBe('false');
    expect(playback.text()).toBe('自动播放');
    await vi.advanceTimersByTimeAsync(15_000);
    expect(wrapper.find('h3').text()).toBe('精选插件一');

    await wrapper.get('button[aria-label="下一个精选"]').trigger('click');
    expect(wrapper.find('h3').text()).toBe('精选插件二');
    await wrapper.get('button[aria-label="自动切换精选"]').trigger('click');
    expect(playback.attributes('aria-pressed')).toBe('true');
    await vi.advanceTimersByTimeAsync(5_000);
    expect(wrapper.find('h3').text()).toBe('精选插件一');
    wrapper.unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
