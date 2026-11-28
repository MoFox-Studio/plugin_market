import { describe, expect, test } from 'vitest'
import fc from 'fast-check'
import type { Audience } from '@/types'
import { audienceMatches } from '@/utils/audience'

function backendFixtureAudienceMatches(
  audience: Audience,
  viewer: { is_admin: boolean } | null,
  viewerHasPlugin: boolean,
): boolean {
  if (audience === 'all') {
    return true
  }
  if (audience === 'logged_in') {
    return viewer !== null
  }
  if (audience === 'anonymous') {
    return viewer === null
  }
  if (audience === 'admins') {
    return viewer !== null && viewer.is_admin
  }
  if (audience === 'authors_with_plugin') {
    return viewer !== null && viewerHasPlugin
  }
  return false
}

describe('audienceMatches 属性测试', () => {
  test('生成的访问者状态与后端受众匹配测试数据的结果一致', () => {
    fc.assert(
      fc.property(
        fc.constantFrom<Audience>('all', 'logged_in', 'anonymous', 'admins', 'authors_with_plugin'),
        fc.boolean(),
        fc.boolean(),
        fc.boolean(),
        (audience, isAuthenticated, isAdmin, viewerHasPlugin) => {
          const viewer = isAuthenticated ? { is_admin: isAdmin } : null

          expect(audienceMatches(audience, viewer, { viewerHasPlugin })).toBe(
            backendFixtureAudienceMatches(audience, viewer, viewerHasPlugin),
          )
        },
      ),
      { numRuns: 100 },
    )
  })
})