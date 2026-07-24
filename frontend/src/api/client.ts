import type { ApiResponse } from '@/types'

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

export const api = {
  login: (username: string, password: string) =>
    request('/api/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request('/api/logout', { method: 'POST' }),
  me: () => request('/api/me'),
  employees: (params = '') => request(`/api/employees${params}`),
  contracts: () => request('/api/contracts'),
  grades: () => request('/api/grades'),
  gradeCatalog: () => request('/api/grade-catalog'),
  passports: () => request('/api/passports'),
  tenure: () => request('/api/tenure'),
  events: (params = '') => request(`/api/events${params}`),
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
  stats: () => request('/api/stats'),
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
}
