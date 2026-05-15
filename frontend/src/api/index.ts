/**
 * API client module - thin wrapper around fetch
 */

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

export const api = {
  get<T = any>(path: string): Promise<T> { return request<T>(path) },
  post<T = any>(path: string, body?: unknown): Promise<T> { return request<T>(path, { method: 'POST', body: body ?? {} }) },
  put<T = any>(path: string, body?: unknown): Promise<T> { return request<T>(path, { method: 'PUT', body: body ?? {} }) },
  del<T = any>(path: string, body?: unknown): Promise<T> { return request<T>(path, { method: 'DELETE', body }) },
}

export default api
