import type { Audience } from '@/types'

export interface AudienceViewer {
  is_admin?: boolean
}

export function audienceMatches(
  audience: Audience,
  viewer: AudienceViewer | null,
  options: { viewerHasPlugin?: boolean } = {},
): boolean {
  const { viewerHasPlugin = false } = options

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
    return viewer !== null && Boolean(viewer.is_admin)
  }
  if (audience === 'authors_with_plugin') {
    return viewer !== null && viewerHasPlugin
  }
  return false
}