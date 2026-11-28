import { afterEach, describe, expect, test, vi } from 'vitest';
import { mount, type VueWrapper } from '@vue/test-utils';
import { nextTick } from 'vue';
import { routeLocationKey } from 'vue-router';
import AnnouncementModal from '@/components/AnnouncementModal.vue';
import SurveyOverprint from '@/components/SurveyOverprint.vue';
import { surveyMiniatures } from '@/composables/surveyMiniatures';
import type { Announcement } from '@/types';

vi.mock('@/composables/useSurveyWorld', async () => {
  const { ref } = await import('vue');
  return {
    SHEET_HEIGHT: 640,
    useSurveyWorld: () => ({
      sheets: ref([0, 2]),
      dimensions: ref({ width: '1600px', height: '1280px' }),
      viewBox: ref('0 0 1600 1280'),
    }),
  };
});

vi.mock('@/composables/surveyMiniatures', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/composables/surveyMiniatures')>();
  return { ...original, surveyMiniatures: vi.fn(original.surveyMiniatures) };
});

const mounted = new Set<VueWrapper>();

afterEach(() => {
  for (const wrapper of mounted) wrapper.unmount();
  mounted.clear();
  vi.clearAllMocks();
});

function buildAnnouncement(severity: string): Announcement {
  return {
    id: 1,
    title: '公告标题',
    body_markdown: '公告正文',
    display_mode: 'modal',
    severity: severity as Announcement['severity'],
    dismissible: true,
    enabled: true,
    audience: 'all',
    emit_inbox: false,
    dismiss_token: 0,
    created_by: 'admin',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  };
}

describe('公告严重级别的中文显示', () => {
  test.each([
    ['info', '通知'],
    ['warning', '警告'],
    ['critical', '严重'],
  ])('严重级别 %s 显示为中文且保留原类名', async (severity, label) => {
    const wrapper = mount(AnnouncementModal, {
      props: { announcement: buildAnnouncement(severity) },
    });
    mounted.add(wrapper);
    await nextTick();

    const kicker = wrapper.get('.announcement-modal-kicker');
    expect(kicker.text()).toBe(label);
    expect(kicker.classes()).toEqual(['announcement-modal-kicker', `is-${severity}`]);
    expect(wrapper.props('announcement').severity).toBe(severity);
  });

  test.each(['future_severity', 'toString'])(
    '未知严重级别 %s 原样回退且保留原类名',
    async (severity) => {
      const wrapper = mount(AnnouncementModal, {
        props: { announcement: buildAnnouncement('info') },
      });
      mounted.add(wrapper);
      await wrapper.setProps({ announcement: buildAnnouncement(severity) });

      const kicker = wrapper.get('.announcement-modal-kicker');
      expect(kicker.text()).toBe(severity);
      expect(kicker.classes()).toEqual(['announcement-modal-kicker', `is-${severity}`]);
      expect(wrapper.props('announcement').severity).toBe(severity);
    },
  );
});

describe('测绘版别只翻译可读文本', () => {
  test.each([
    { route: 'home', code: 'RIDGE', label: '山脊', symbol: 'pass', x: '1000', y: '227' },
    { route: 'market', code: 'ATLAS', label: '图集', symbol: 'chart', x: '940', y: '192' },
    { route: 'plugin', code: 'PROOF', label: '校样', symbol: 'proof', x: '1035', y: '277' },
    { route: 'status', code: 'RELAY', label: '中继', symbol: 'relay', x: '980', y: '217' },
  ])('$code 显示为$label，保留版别属性与图形输入', ({ route, code, label, symbol, x, y }) => {
    const wrapper = mount(SurveyOverprint, {
      global: { provide: { [routeLocationKey as symbol]: { name: route } } },
    });
    mounted.add(wrapper);

    expect(wrapper.findAll('text[x="-52"]').map((node) => node.text())).toEqual([
      `${label} / 001`,
      `${label} / 003`,
    ]);
    expect(wrapper.attributes('data-edition')).toBe(code);
    expect(surveyMiniatures).toHaveBeenCalledTimes(2);
    expect(surveyMiniatures).toHaveBeenNthCalledWith(1, 0, code);
    expect(surveyMiniatures).toHaveBeenNthCalledWith(2, 2, code);

    const discovery = wrapper.get('.survey-discovery');
    expect(discovery.attributes('href')).toMatch(new RegExp(`#${symbol}$`));
    expect(discovery.attributes('x')).toBe(x);
    expect(discovery.attributes('y')).toBe(y);
    const miniatures = vi.mocked(surveyMiniatures).mock.results.flatMap((result) => result.value);
    expect(wrapper.findAll('.survey-miniature').map((node) => node.attributes('href'))).toEqual(
      miniatures.map((miniature) => miniature.source),
    );
  });
});
