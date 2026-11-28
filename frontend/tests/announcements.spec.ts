import { beforeEach, describe, expect, test, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const dismissMock = vi.hoisted(() => vi.fn())

vi.mock('@/api', () => ({
  default: {
    announcements: {
      dismiss: dismissMock,
    },
  },
}))

import { useAnnouncementsStore } from '@/stores/announcements'
import type { Announcement } from '@/types'

const STORAGE_KEY = 'plugin-market:announcement-dismissals:v1'

function buildAnnouncement(id: number, dismissToken = 0): Announcement {
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
    dismiss_token: dismissToken,
    created_by: 'admin',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }
}

function readDismissals(): Record<number, number> {
  const raw = window.localStorage.getItem(STORAGE_KEY)
  return raw ? (JSON.parse(raw) as Record<number, number>) : {}
}

describe('announcements store dismissal persistence', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    window.localStorage.clear()
    dismissMock.mockReset()
  })

  test('keeps a local dismissal when the API rejects anonymous viewers', async () => {
    dismissMock.mockRejectedValueOnce(new Error('GitHub login is required.'))
    const store = useAnnouncementsStore()
    store.items = [buildAnnouncement(2)]

    await expect(store.dismiss(2)).resolves.toBeUndefined()

    expect(readDismissals()).toMatchObject({ 2: 0 })
    expect(store.visibleItems).toHaveLength(0)
  })

  test('records the server dismiss token on success', async () => {
    dismissMock.mockResolvedValueOnce({
      announcement_id: 2,
      dismissed: true,
      dismiss_token: 3,
    })
    const store = useAnnouncementsStore()
    store.items = [buildAnnouncement(2, 3)]

    await store.dismiss(2)

    expect(dismissMock).toHaveBeenCalledWith(2)
    expect(readDismissals()).toMatchObject({ 2: 3 })
    expect(store.visibleItems).toHaveLength(0)
  })
})