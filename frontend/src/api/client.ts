import { ApiError } from '@/api/errors'
import { localizeApiMessage } from '@/utils/labels'
import type {
  ApiResponse,
  AttentionSummary,
  DashboardStats,
  Paginated,
  SearchResponse,
} from '@/types'

export interface TableQueryParams {
  page?: number
  per_page?: number
  q?: string
  sort?: string
  direction?: 'asc' | 'desc'
  [key: string]: string | number | boolean | undefined
}

export function buildQuery(params: TableQueryParams = {}): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

async function parseJsonResponse<T>(response: Response): Promise<ApiResponse<T>> {
  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) {
    throw new ApiError(
      localizeApiMessage(response.status === 401 ? 'Invalid credentials' : undefined),
      response.status,
    )
  }
  return (await response.json()) as ApiResponse<T>
}

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
    ...options,
  })

  const payload = await parseJsonResponse<T>(response)
  if (!response.ok || !payload.success) {
    throw new ApiError(localizeApiMessage(payload.message), response.status, payload.message)
  }
  return payload.data as T
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export const api = {
  login: (username: string, password: string) =>
    request('/api/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request('/api/logout', { method: 'POST' }),
  me: () => request('/api/me'),
  employees: (params: TableQueryParams = {}) =>
    request<Paginated<unknown>>(`/api/employees${buildQuery(params)}`),
  createEmployee: (body: Record<string, unknown>) =>
    request('/api/employees', { method: 'POST', body: JSON.stringify(body) }),
  updateEmployee: (id: number, body: Record<string, unknown>) =>
    request(`/api/employees/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteEmployee: (id: number) => request(`/api/employees/${id}`, { method: 'DELETE' }),
  contracts: (params: TableQueryParams = {}) =>
    request<Paginated<unknown>>(`/api/contracts${buildQuery(params)}`),
  grades: (params: TableQueryParams = {}) =>
    request<Paginated<unknown>>(`/api/grades${buildQuery(params)}`),
  gradeCatalog: () => request('/api/grade-catalog'),
  createGradeCatalog: (body: { name: string; rank: number; min_months?: number }) =>
    request('/api/grade-catalog', { method: 'POST', body: JSON.stringify(body) }),
  passports: (params: TableQueryParams = {}) =>
    request<Paginated<unknown>>(`/api/passports${buildQuery(params)}`),
  tenure: (params: TableQueryParams = {}) =>
    request<Paginated<unknown>>(`/api/tenure${buildQuery(params)}`),
  rewards: (params: TableQueryParams = {}) =>
    request<Paginated<unknown>>(`/api/rewards${buildQuery(params)}`),
  createReward: (body: Record<string, unknown>) =>
    request('/api/rewards', { method: 'POST', body: JSON.stringify(body) }),
  updateReward: (id: number, body: Record<string, unknown>) =>
    request(`/api/rewards/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  events: (params: TableQueryParams = {}) =>
    request<Paginated<unknown>>(`/api/events${buildQuery(params)}`),
  upcomingEvents: (limit = 10) => request(`/api/events/upcoming?limit=${limit}`),
  createEvent: (body: Record<string, unknown>) =>
    request('/api/events', { method: 'POST', body: JSON.stringify(body) }),
  completeEvent: (id: number, comment?: string) =>
    request(`/api/events/${id}/complete`, {
      method: 'POST',
      body: JSON.stringify({ comment }),
    }),
  notificationRules: () => request('/api/notifications/rules'),
  createNotificationRule: (body: Record<string, unknown>) =>
    request('/api/notifications/rules', { method: 'POST', body: JSON.stringify(body) }),
  testNotification: (body: Record<string, unknown>) =>
    request('/api/notifications/test', { method: 'POST', body: JSON.stringify(body) }),
  stats: (params: TableQueryParams = {}) =>
    request<DashboardStats>(`/api/stats${buildQuery(params)}`),
  attention: (params: TableQueryParams = {}) =>
    request<AttentionSummary>(`/api/attention${buildQuery(params)}`),
  search: (q: string, limit = 20) =>
    request<SearchResponse>(`/api/search${buildQuery({ q, limit })}`),
  getImportJob: (jobId: number) => request(`/api/import/${jobId}`),
  uploadImport: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    const response = await fetch('/api/import/upload', {
      method: 'POST',
      credentials: 'include',
      body: form,
    })
    const payload = await parseJsonResponse<unknown>(response)
    if (!response.ok || !payload.success) {
      throw new ApiError(localizeApiMessage(payload.message), response.status, payload.message)
    }
    return payload.data
  },
  confirmImport: (jobId: number, rowActions: Record<number, string>) =>
    request(`/api/import/${jobId}/confirm`, {
      method: 'POST',
      body: JSON.stringify({ row_actions: rowActions }),
    }),
  downloadImportTemplate: async (companyId = 1) => {
    const response = await fetch(`/api/import/template?company_id=${companyId}`, {
      credentials: 'include',
    })
    if (!response.ok) {
      let message = 'Не удалось скачать шаблон'
      try {
        const payload = await parseJsonResponse<unknown>(response)
        message = localizeApiMessage(payload.message) ?? message
      } catch {
        // ignore non-json error body
      }
      throw new ApiError(message, response.status)
    }
    const blob = await response.blob()
    triggerDownload(blob, 'employees_template.xlsx')
  },
}
