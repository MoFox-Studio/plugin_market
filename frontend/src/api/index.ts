/**
 * API client module - thin wrapper around fetch
 */

import type {
  Announcement,
  AnnouncementCreate,
  AnnouncementDismissResponse,
  AnnouncementListResponse,
  AnnouncementUpdate,
  AccessTokenRotateResponse,
  AccessTokenStatus,
  AuthorFollowState,
  AuthorProfile,
  AuthorProfileUpdate,
  BulkActionRequest,
  BulkActionResult,
  CurationEntry,
  CurationEntryCreate,
  CurationEntryListResponse,
  CurationEntryUpdate,
  InboxMessageListResponse,
  InboxUnreadCount,
  MarketHome,
  MentionCandidate,
  MyFollowListResponse,
  MySubscriptionListResponse,
  PinCreate,
  PinnedPlugin,
  PinUpdate,
  Plugin,
  PluginSubscriptionState,
  PluginMetadataPatch,
  Skill,
  SkillComment,
  SkillCommentCreate,
  SkillCommentListResponse,
  SkillInstallRecord,
  SkillListResponse,
  SkillRatingInfo,
  SkillUpdate,
  SkillVersion,
  SkillVersionListResponse,
} from '@/types'

export class ApiError extends Error {
  status: number
  code: string | undefined

  constructor(message: string, status: number, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

interface RequestOptions {
  method?: string
  body?: unknown
  expect?: 'json' | 'text'
}

type QueryValue = string | number | boolean | null | undefined

function withQuery(path: string, query?: Record<string, QueryValue>): string {
  if (!query) {
    return path
  }

  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') {
      continue
    }
    params.set(key, String(value))
  }

  const queryString = params.toString()
  if (!queryString) {
    return path
  }
  return `${path}${path.includes('?') ? '&' : '?'}${queryString}`
}

async function request<T = any>(path: string, { method = 'GET', body, expect = 'json' }: RequestOptions = {}): Promise<T> {
  const opts: RequestInit = { method, credentials: 'include', headers: {} }
  if (body !== undefined) {
    (opts.headers as Record<string, string>)['Content-Type'] = 'application/json'
    opts.body = typeof body === 'string' ? body : JSON.stringify(body)
  }
  const r = await fetch(path, opts)
  if (r.status === 204) return null as T
  const data = expect === 'json' ? await r.json().catch(() => null) : await r.text()
  if (!r.ok) {
    throw new ApiError(
      data?.error?.message || r.statusText || 'Request failed',
      r.status,
      data?.error?.code
    )
  }
  return data as T
}

function get<T = any>(path: string): Promise<T> { return request<T>(path) }
function post<T = any>(path: string, body?: unknown): Promise<T> { return request<T>(path, { method: 'POST', body: body ?? {} }) }
function put<T = any>(path: string, body?: unknown): Promise<T> { return request<T>(path, { method: 'PUT', body: body ?? {} }) }
function patch<T = any>(path: string, body?: unknown): Promise<T> { return request<T>(path, { method: 'PATCH', body: body ?? {} }) }
function del<T = any>(path: string, body?: unknown): Promise<T> { return request<T>(path, { method: 'DELETE', body }) }

async function upload<T = any>(path: string, file: File, fieldName = 'file'): Promise<T> {
  const form = new FormData()
  form.append(fieldName, file)
  const r = await fetch(path, { method: 'POST', credentials: 'include', body: form })
  const data = await r.json().catch(() => null)
  if (!r.ok) {
    throw new ApiError(
      data?.error?.message || r.statusText || 'Upload failed',
      r.status,
      data?.error?.code,
    )
  }
  return data as T
}

async function uploadForm<T = any>(path: string, formData: FormData): Promise<T> {
  const r = await fetch(path, { method: 'POST', credentials: 'include', body: formData })
  const data = await r.json().catch(() => null)
  if (!r.ok) {
    throw new ApiError(
      data?.error?.message || r.statusText || 'Upload failed',
      r.status,
      data?.error?.code,
    )
  }
  return data as T
}

export const api = {
  get,
  post,
  put,
  patch,
  del,

  market: {
    home(): Promise<MarketHome> {
      return get<MarketHome>('/api/v1/market/home')
    },
  },

  inbox: {
    list(query?: { type?: string; offset?: number; limit?: number }): Promise<InboxMessageListResponse> {
      return get<InboxMessageListResponse>(withQuery('/api/v1/inbox/messages', query))
    },
    unreadCount(): Promise<InboxUnreadCount> {
      return get<InboxUnreadCount>('/api/v1/inbox/unread-count')
    },
    markRead(messageId: number): Promise<{ updated: number }> {
      return post<{ updated: number }>(`/api/v1/inbox/messages/${messageId}/read`)
    },
    markAllRead(): Promise<{ updated: number }> {
      return post<{ updated: number }>('/api/v1/inbox/read-all')
    },
  },

  announcements: {
    active(): Promise<Announcement[]> {
      return get<Announcement[]>('/api/v1/announcements/active')
    },
    dismiss(announcementId: number): Promise<AnnouncementDismissResponse> {
      return post<AnnouncementDismissResponse>(`/api/v1/announcements/${announcementId}/dismiss`)
    },
  },

  me: {
    profile: {
      get(): Promise<AuthorProfile> {
        return get<AuthorProfile>('/api/v1/me/profile')
      },
      update(payload: AuthorProfileUpdate): Promise<AuthorProfile> {
        return put<AuthorProfile>('/api/v1/me/profile', payload)
      },
      uploadBackground(file: File): Promise<AuthorProfile> {
        return upload<AuthorProfile>('/api/v1/me/profile/background', file)
      },
    },
    pins: {
      list(): Promise<PinnedPlugin[]> {
        return get<PinnedPlugin[]>('/api/v1/me/pins')
      },
      add(payload: PinCreate): Promise<PinnedPlugin> {
        return post<PinnedPlugin>('/api/v1/me/pins', payload)
      },
      update(pluginId: string, payload: PinUpdate): Promise<PinnedPlugin> {
        return put<PinnedPlugin>(`/api/v1/me/pins/${encodeURIComponent(pluginId)}`, payload)
      },
      remove(pluginId: string): Promise<null> {
        return del<null>(`/api/v1/me/pins/${encodeURIComponent(pluginId)}`)
      },
    },
    plugins: {
      patchMetadata(pluginId: string, payload: PluginMetadataPatch): Promise<Plugin> {
        return patch<Plugin>(`/api/v1/me/plugins/${encodeURIComponent(pluginId)}/metadata`, payload)
      },
      uploadIcon(pluginId: string, file: File): Promise<Plugin> {
        return upload<Plugin>(`/api/v1/me/plugins/${encodeURIComponent(pluginId)}/icon`, file)
      },
    },
    accessToken: {
      get(): Promise<AccessTokenStatus> {
        return get<AccessTokenStatus>('/api/v1/me/access-token')
      },
      rotate(): Promise<AccessTokenRotateResponse> {
        return post<AccessTokenRotateResponse>('/api/v1/me/access-token')
      },
      revoke(): Promise<AccessTokenStatus> {
        return del<AccessTokenStatus>('/api/v1/me/access-token')
      },
    },
    subscriptions(): Promise<MySubscriptionListResponse> {
      return get<MySubscriptionListResponse>('/api/v1/me/subscriptions')
    },
    follows(): Promise<MyFollowListResponse> {
      return get<MyFollowListResponse>('/api/v1/me/follows')
    },
  },

  authors: {
    search(prefix: string, limit = 8): Promise<MentionCandidate[]> {
      return get<MentionCandidate[]>(withQuery('/api/v1/authors/search', { prefix, limit }))
    },
    followState(authorId: string): Promise<AuthorFollowState> {
      return get<AuthorFollowState>(`/api/v1/authors/${encodeURIComponent(authorId)}/follow`)
    },
    toggleFollow(authorId: string): Promise<AuthorFollowState> {
      return post<AuthorFollowState>(`/api/v1/authors/${encodeURIComponent(authorId)}/follow`)
    },
  },

  plugins: {
    toggleSubscription(pluginId: string): Promise<PluginSubscriptionState> {
      return post<PluginSubscriptionState>(`/api/v1/plugins/${encodeURIComponent(pluginId)}/subscribe`)
    },
  },

  skills: {
    list(params?: Record<string, QueryValue>): Promise<SkillListResponse> {
      return get<SkillListResponse>(withQuery('/api/v1/skills', params))
    },
    get(skillId: string): Promise<Skill> {
      return get<Skill>(`/api/v1/skills/${encodeURIComponent(skillId)}`)
    },
    versions(skillId: string): Promise<SkillVersionListResponse> {
      return get<SkillVersionListResponse>(`/api/v1/skills/${encodeURIComponent(skillId)}/versions`)
    },
    version(skillId: string, version: string): Promise<SkillVersion> {
      return get<SkillVersion>(`/api/v1/skills/${encodeURIComponent(skillId)}/versions/${encodeURIComponent(version)}`)
    },
    downloadUrl(skillId: string, version: string): string {
      return `/api/v1/skills/${encodeURIComponent(skillId)}/versions/${encodeURIComponent(version)}/download`
    },
    comments(skillId: string, params?: Record<string, QueryValue>): Promise<SkillCommentListResponse> {
      return get<SkillCommentListResponse>(withQuery(`/api/v1/skills/${encodeURIComponent(skillId)}/comments`, params))
    },
    postComment(skillId: string, payload: SkillCommentCreate): Promise<SkillComment> {
      return post<SkillComment>(`/api/v1/skills/${encodeURIComponent(skillId)}/comments`, payload)
    },
    deleteComment(skillId: string, commentId: number): Promise<void> {
      return del(`/api/v1/skills/${encodeURIComponent(skillId)}/comments/${commentId}`)
    },
    rating(skillId: string): Promise<SkillRatingInfo> {
      return get<SkillRatingInfo>(`/api/v1/skills/${encodeURIComponent(skillId)}/rating`)
    },
    postRating(skillId: string, score: number): Promise<SkillRatingInfo> {
      return post<SkillRatingInfo>(`/api/v1/skills/${encodeURIComponent(skillId)}/rating`, { score })
    },
    deleteRating(skillId: string): Promise<void> {
      return del(`/api/v1/skills/${encodeURIComponent(skillId)}/rating`)
    },
    toggleLike(skillId: string): Promise<{ liked: boolean }> {
      return post<{ liked: boolean }>(`/api/v1/skills/${encodeURIComponent(skillId)}/like`)
    },
    subscribe(skillId: string): Promise<{ subscribed: boolean }> {
      return post<{ subscribed: boolean }>(`/api/v1/skills/${encodeURIComponent(skillId)}/subscribe`)
    },
    recordInstall(skillId: string): Promise<SkillInstallRecord> {
      return post<SkillInstallRecord>(`/api/v1/skills/${encodeURIComponent(skillId)}/install-record`)
    },
    create(formData: FormData): Promise<Skill> {
      return uploadForm<Skill>('/api/v1/skills', formData)
    },
    publishVersion(skillId: string, formData: FormData): Promise<SkillVersion> {
      return uploadForm<SkillVersion>(`/api/v1/skills/${encodeURIComponent(skillId)}/versions`, formData)
    },
    update(skillId: string, payload: SkillUpdate): Promise<Skill> {
      return put<Skill>(`/api/v1/skills/${encodeURIComponent(skillId)}`, payload)
    },
    delete(skillId: string): Promise<void> {
      return del(`/api/v1/skills/${encodeURIComponent(skillId)}`)
    },
    my(): Promise<Skill[]> {
      return get<Skill[]>('/api/v1/me/skills')
    },
    categories(): Promise<string[]> {
      return get<{ items: string[] }>('/api/v1/skills/categories').then(r => r.items)
    },
    tags(): Promise<string[]> {
      return get<{ items: string[] }>('/api/v1/skills/tags').then(r => r.items)
    },
  },

  admin: {
    announcements: {
      list(query?: { offset?: number; limit?: number }): Promise<AnnouncementListResponse> {
        return get<AnnouncementListResponse>(withQuery('/api/v1/admin/announcements', query))
      },
      create(payload: AnnouncementCreate): Promise<Announcement> {
        return post<Announcement>('/api/v1/admin/announcements', payload)
      },
      update(announcementId: number, payload: AnnouncementUpdate): Promise<Announcement> {
        return put<Announcement>(`/api/v1/admin/announcements/${announcementId}`, payload)
      },
      disable(announcementId: number): Promise<Announcement> {
        return post<Announcement>(`/api/v1/admin/announcements/${announcementId}/disable`)
      },
      resurface(announcementId: number): Promise<Announcement> {
        return post<Announcement>(`/api/v1/admin/announcements/${announcementId}/resurface`)
      },
    },
    curation: {
      list(): Promise<CurationEntryListResponse> {
        return get<CurationEntryListResponse>('/api/v1/admin/curation/entries')
      },
      create(payload: CurationEntryCreate): Promise<CurationEntry> {
        return post<CurationEntry>('/api/v1/admin/curation/entries', payload)
      },
      update(entryId: number, payload: CurationEntryUpdate): Promise<CurationEntry> {
        return put<CurationEntry>(`/api/v1/admin/curation/entries/${entryId}`, payload)
      },
      disable(entryId: number): Promise<CurationEntry> {
        return post<CurationEntry>(`/api/v1/admin/curation/entries/${entryId}/disable`)
      },
      reorder(idsInOrder: number[]): Promise<CurationEntry[]> {
        return put<CurationEntry[]>('/api/v1/admin/curation/order', { ids_in_order: idsInOrder })
      },
    },
    bulkApply(payload: BulkActionRequest): Promise<BulkActionResult> {
      return post<BulkActionResult>('/api/v1/admin/plugins/bulk', payload)
    },
  },
}

export default api
