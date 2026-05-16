import '@/assets/tokens.css'

import { beforeEach, describe, expect, test, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import fc from 'fast-check'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import App from '@/App.vue'
import FeaturedShowcase from '@/components/FeaturedShowcase.vue'
import { useAnnouncementsStore } from '@/stores/announcements'
import { useAuthStore } from '@/stores/auth'
import { useInboxStore } from '@/stores/inbox'
import type { Plugin } from '@/types'

function installMatchMedia(matchesReduce: boolean): void {
  vi.stubGlobal('matchMedia', vi.fn((query: string) => ({
    matches: query === '(prefers-reduced-motion: reduce)' ? matchesReduce : false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })))
}

function buildPlugin(id: number): Plugin {
  return {
    plugin_id: `plug-${id}`,
    display_name: `Plugin ${id}`,
    summary: 'summary',
    status: 'published',
    trust_level: 'community',
    owner_id: 'owner',
    repository_url: 'https://github.com/MoFox-Studio/sample',
    maintainers: [],
    likes_count: 0,
    downloads_count: 0,
    comments_count: 0,
    rating_avg: 0,
    rating_count: 0,
    updated_at: '2026-01-01T00:00:00Z',
  }
}

describe('reduced motion property', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.documentElement.dataset.reducedMotion = 'no-preference'
    window.localStorage.clear()
    vi.restoreAllMocks()
  })

  test('reduced motion tokens stay within 80ms and carousel autoplay does not start', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uniqueArray(fc.integer({ min: 1, max: 50 }), { maxLength: 8 }),
        async (ids) => {
          installMatchMedia(true)

          const announcements = useAnnouncementsStore()
          announcements.loadActive = vi.fn(async () => [])
          const auth = useAuthStore()
          auth.loadViewer = vi.fn()
          const inbox = useInboxStore()
          inbox.startPolling = vi.fn()
          inbox.stopPolling = vi.fn()

          const appWrapper = mount(App, {
            global: {
              stubs: {
                AppToast: true,
                DisclaimerModal: true,
                AppShell: { template: '<div><slot /></div>' },
                RouterView: true,
              },
            },
          })
          await nextTick()

          expect(document.documentElement.dataset.reducedMotion).toBe('reduce')

          const style = getComputedStyle(document.documentElement)
          const fast = parseFloat(style.getPropertyValue('--dur-fast')) || 0
          const base = parseFloat(style.getPropertyValue('--dur-base')) || 0
          const slow = parseFloat(style.getPropertyValue('--dur-slow')) || 0
          expect(fast).toBeLessThanOrEqual(80)
          expect(base).toBeLessThanOrEqual(80)
          expect(slow).toBeLessThanOrEqual(80)

          const setIntervalSpy = vi.spyOn(window, 'setInterval')
          const showcaseWrapper = mount(FeaturedShowcase, {
            props: {
              items: ids.map((id) => buildPlugin(id)),
            },
            global: {
              stubs: {
                PluginCard: { template: '<div class="plugin-card-stub"></div>' },
              },
            },
          })
          await nextTick()

          expect(setIntervalSpy).not.toHaveBeenCalled()

          showcaseWrapper.unmount()
          appWrapper.unmount()
        },
      ),
      { numRuns: 20 },
    )
  })
})