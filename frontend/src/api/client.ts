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

let csrfToken: string | null = null
let unauthorizedHandler: (() => void) | null = null

export function setCsrfToken(token: string | null) {
  csrfToken = token
}

export function getCsrfToken(): string | null {
  return csrfToken
}

export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler
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
      localizeApiMessage(response.status === 401 ? 'Unauthorized' : undefined),
      response.status,
    )
  }
  return (await response.json()) as ApiResponse<T>
}

function buildHeaders(options: RequestInit, isJsonBody: boolean): HeadersInit {
  const headers: Record<string, string> = {
    ...(isJsonBody ? { 'Content-Type': 'application/json' } : {}),
    ...(options.headers as Record<string, string> | undefined),
  }
  if (csrfToken && options.method && options.method !== 'GET') {
    headers['X-CSRF-Token'] = csrfToken
  }
  return headers
}

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const isJsonBody = Boolean(options.body) && !(options.body instanceof FormData)
  const response = await fetch(url, {
    credentials: 'include',
    headers: buildHeaders(options, isJsonBody),
    ...options,
  })

  if (response.status === 401 && !url.endsWith('/api/login')) {
    unauthorizedHandler?.()
  }

  const payload = await parseJsonResponse<T>(response)
  if (!response.ok || !payload.success) {
    throw new ApiError(localizeApiMessage(payload.message), response.status, payload.message)
  }

  if (payload.data && typeof payload.data === 'object' && 'csrf_token' in payload.data) {
    const token = (payload.data as { csrf_token?: string }).csrf_token
    if (token) setCsrfToken(token)
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
  fetchCsrf: () =>
    request<{ csrf_token: string }>('/api/csrf').then((data) => {
      if (data?.csrf_token) setCsrfToken(data.csrf_token)
      return data
    }),
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
  createContract: (body: {
    employment_id: number
    start_date: string
    end_date?: string | null
    term_years?: number | null
    notes?: string | null
  }) => request('/api/contracts', { method: 'POST', body: JSON.stringify(body) }),
  updateContract: (
    id: number,
    body: Partial<{
      start_date: string
      end_date: string
      term_years: number
      notes: string
    }>,
  ) => request(`/api/contracts/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  grades: (params: TableQueryParams = {}) =>
    request<Paginated<unknown>>(`/api/grades${buildQuery(params)}`),
  gradeCatalog: () => request('/api/grade-catalog'),
  createGradeCatalog: (body: {
    name: string
    rank: number
    min_years?: number
    extra_year_without_university?: boolean
  }) =>
    request('/api/grade-catalog', { method: 'POST', body: JSON.stringify(body) }),
  updateGradeCatalog: (
    id: number,
    body: Partial<{
      name: string
      rank: number
      min_years: number
      extra_year_without_university: boolean
      is_active: boolean
    }>,
  ) =>
    request(`/api/grade-catalog/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteGradeCatalog: (id: number) =>
    request(`/api/grade-catalog/${id}`, { method: 'DELETE' }),
  assignGrade: (body: {
    employment_id: number
    grade_id: number
    assigned_date: string
    basis?: string
  }) => request('/api/grades/assign', { method: 'POST', body: JSON.stringify(body) }),
  passports: (params: TableQueryParams = {}) =>
    request<Paginated<unknown>>(`/api/passports${buildQuery(params)}`),
  tenure: (params: TableQueryParams = {}) =>
    request<Paginated<unknown>>(`/api/tenure${buildQuery(params)}`),
  updateTenureAward: (
    id: number,
    body: { is_received?: boolean; received_date?: string | null },
  ) => request(`/api/tenure/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  rewards: (params: TableQueryParams = {}) =>
    request<Paginated<unknown>>(`/api/rewards${buildQuery(params)}`),
  createReward: (body: Record<string, unknown>) =>
    request('/api/rewards', { method: 'POST', body: JSON.stringify(body) }),
  updateReward: (id: number, body: Record<string, unknown>) =>
    request(`/api/rewards/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  events: (params: TableQueryParams = {}) =>
    request<Paginated<unknown>>(`/api/events${buildQuery(params)}`),
  getEvent: (id: number) => request(`/api/events/${id}`),
  upcomingEvents: (limit = 10) => request(`/api/events/upcoming?limit=${limit}`),
  createEvent: (body: Record<string, unknown>) =>
    request('/api/events', { method: 'POST', body: JSON.stringify(body) }),
  updateEvent: (id: number, body: Record<string, unknown>) =>
    request(`/api/events/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteEvent: (id: number) =>
    request(`/api/events/${id}`, { method: 'DELETE' }),
  completeEvent: (
    id: number,
    comment?: string,
    options?: {
      extension_term_years?: number | null
      new_end_date?: string | null
      target_grade_id?: number | null
    },
  ) =>
    request(`/api/events/${id}/complete`, {
      method: 'POST',
      body: JSON.stringify({
        comment,
        ...(options?.extension_term_years !== undefined
          ? { extension_term_years: options.extension_term_years }
          : {}),
        ...(options?.new_end_date !== undefined ? { new_end_date: options.new_end_date } : {}),
        ...(options?.target_grade_id !== undefined
          ? { target_grade_id: options.target_grade_id }
          : {}),
      }),
    }),
  cancelEvent: (id: number, comment?: string) =>
    request(`/api/events/${id}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ comment }),
    }),
  reopenEvent: (id: number) =>
    request(`/api/events/${id}/reopen`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),
  notificationRules: () => request('/api/notifications/rules'),
  createNotificationRule: (body: Record<string, unknown>) =>
    request('/api/notifications/rules', { method: 'POST', body: JSON.stringify(body) }),
  updateNotificationRule: (id: number, body: Record<string, unknown>) =>
    request(`/api/notifications/rules/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  testNotification: (body: Record<string, unknown>) =>
    request('/api/notifications/test', { method: 'POST', body: JSON.stringify(body) }),
  roles: () => request('/api/roles'),
  users: (params: TableQueryParams = {}) =>
    request<Paginated<unknown>>(`/api/users${buildQuery(params)}`),
  createUser: (body: {
    username: string
    password: string
    full_name: string
    role: string
  }) => request('/api/users', { method: 'POST', body: JSON.stringify(body) }),
  updateUser: (
    id: number,
    body: Partial<{ full_name: string; role: string; is_active: boolean }>,
  ) => request(`/api/users/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  unlockUser: (id: number) =>
    request(`/api/users/${id}/unlock`, { method: 'POST', body: JSON.stringify({}) }),
  resetUserPassword: (id: number, password: string) =>
    request(`/api/users/${id}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ password }),
    }),
  stats: (params: TableQueryParams = {}) =>
    request<DashboardStats>(`/api/stats${buildQuery(params)}`),
  attention: (params: TableQueryParams = {}) =>
    request<AttentionSummary>(`/api/attention${buildQuery(params)}`),
  search: (q: string, limit = 20) =>
    request<SearchResponse>(`/api/search${buildQuery({ q, limit })}`),
  getImportJob: (jobId: number) => request(`/api/import/${jobId}`),
  uploadImport: async (file: File, importType: 'employees' | 'rewards' = 'employees') => {
    const form = new FormData()
    form.append('file', file)
    form.append('import_type', importType)
    const response = await fetch('/api/import/upload', {
      method: 'POST',
      credentials: 'include',
      headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : {},
      body: form,
    })
    if (response.status === 401) {
      unauthorizedHandler?.()
    }
    const payload = await parseJsonResponse<unknown>(response)
    if (!response.ok || !payload.success) {
      throw new ApiError(localizeApiMessage(payload.message), response.status, payload.message)
    }
    return payload.data
  },
  confirmImport: (
    jobId: number,
    rowActions: Record<number, string>,
    options: { markReachedTenure?: boolean; updateExistingTenure?: boolean } = {},
  ) =>
    request(`/api/import/${jobId}/confirm`, {
      method: 'POST',
      body: JSON.stringify({
        row_actions: rowActions,
        mark_reached_tenure: options.markReachedTenure ?? true,
        update_existing_tenure: options.updateExistingTenure ?? true,
      }),
    }),
  revalidateImport: (jobId: number) =>
    request(`/api/import/${jobId}/revalidate`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),
  downloadImportTemplate: async (
    companyId = 1,
    importType: 'employees' | 'rewards' = 'employees',
  ) => {
    const response = await fetch(
      `/api/import/template?company_id=${companyId}&import_type=${importType}`,
      {
        credentials: 'include',
      },
    )
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
    const filename =
      importType === 'rewards' ? 'rewards_template.xlsx' : 'employees_template.xlsx'
    triggerDownload(blob, filename)
  },
}
