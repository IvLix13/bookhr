import type { ApiResponse, DashboardStats, Paginated } from '@/types'

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
    ...options,
  })

  const payload = (await response.json()) as ApiResponse<T>
  if (!response.ok || !payload.success) {
    throw new Error(payload.message ?? `Request failed: ${response.status}`)
  }
  return payload.data as T
}

async function fetchAllPaginated<T>(
  fetchPage: (params: string) => Promise<Paginated<T>>,
  perPage = 200,
): Promise<T[]> {
  const first = await fetchPage(`?page=1&per_page=${perPage}`)
  const all = [...first.items]
  for (let page = 2; page <= first.pages; page += 1) {
    const data = await fetchPage(`?page=${page}&per_page=${perPage}`)
    all.push(...data.items)
  }
  return all
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
  employees: (params = '') => request(`/api/employees${params}`),
  fetchAllEmployees: () =>
    fetchAllPaginated((params) => api.employees(params) as Promise<Paginated<unknown>>),
  createEmployee: (body: Record<string, unknown>) =>
    request('/api/employees', { method: 'POST', body: JSON.stringify(body) }),
  updateEmployee: (id: number, body: Record<string, unknown>) =>
    request(`/api/employees/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteEmployee: (id: number) =>
    request(`/api/employees/${id}`, { method: 'DELETE' }),
  contracts: () => request('/api/contracts'),
  grades: () => request('/api/grades'),
  gradeCatalog: () => request('/api/grade-catalog'),
  createGradeCatalog: (body: { name: string; rank: number; min_months?: number }) =>
    request('/api/grade-catalog', { method: 'POST', body: JSON.stringify(body) }),
  passports: () => request('/api/passports'),
  tenure: () => request('/api/tenure'),
  rewards: () => request('/api/rewards'),
  createReward: (body: Record<string, unknown>) =>
    request('/api/rewards', { method: 'POST', body: JSON.stringify(body) }),
  updateReward: (id: number, body: Record<string, unknown>) =>
    request(`/api/rewards/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  events: (params = '') => request(`/api/events${params}`),
  fetchAllEvents: () =>
    fetchAllPaginated((params) => api.events(params) as Promise<Paginated<unknown>>),
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
  stats: (params = '') => request<DashboardStats>(`/api/stats${params}`),
  uploadImport: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    const response = await fetch('/api/import/upload', {
      method: 'POST',
      credentials: 'include',
      body: form,
    })
    const payload = await response.json()
    if (!response.ok || !payload.success) {
      throw new Error(payload.message ?? 'Upload failed')
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
        const payload = await response.json()
        message = payload.message ?? message
      } catch {
        // ignore non-json error body
      }
      throw new Error(message)
    }
    const blob = await response.blob()
    triggerDownload(blob, 'employees_template.xlsx')
  },
}
