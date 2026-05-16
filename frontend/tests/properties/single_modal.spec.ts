import { beforeEach, describe, expect, test } from 'vitest'
import { mount } from '@vue/test-utils'
import fc from 'fast-check'
import { createPinia, setActivePinia } from 'pinia'
import AnnouncementModalQueue from '@/components/AnnouncementModalQueue.vue'
import { useAnnouncementsStore } from '@/stores/announcements'
import type { Announcement } from '@/types'

function buildAnnouncement(id: number): Announcement {
  return {
    id,
    title: `Announcement ${id}`,
    body_markdown: 'Body',
    display_mode: 'modal',
    severity: 'info',
    dismissible: true,
    enabled: true,
    starts_at: null,
    ends_at: null,
    audience: 'all',
    emit_inbox: false,
    dismiss_token: 0,
    created_by: 'admin',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }
}

describe('AnnouncementModalQueue property', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    window.localStorage.clear()
  })

  test('renders at most one modal for any active modal set', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uniqueArray(fc.integer({ min: 1, max: 500 }), { selector: (value) => value, maxLength: 12 }),
        async (ids) => {
          const store = useAnnouncementsStore()
          store.items = ids.map((id) => buildAnnouncement(id))

          const wrapper = mount(AnnouncementModalQueue, {
            global: {
              stubs: {
                AnnouncementModal: {
                  props: ['announcement'],
                  template: '<div data-testid="modal">{{ announcement.id }}</div>',
                },
              },
            },
          })

          const modals = wrapper.findAll('[data-testid="modal"]')
          expect(modals.length).toBeLessThanOrEqual(1)
          expect(modals.length).toBe(ids.length ? 1 : 0)
          if (ids.length) {
            expect(modals[0]?.text()).toBe(String(ids[0]))
          }

          wrapper.unmount()
        },
      ),
      { numRuns: 30 },
    )
  })
})