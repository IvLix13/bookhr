import { ApiError } from '@/api/errors'
import { buildQuery, getCsrfToken } from '@/api/client'
import { localizeApiMessage } from '@/utils/labels'
import type { Paginated } from '@/types'

export interface AttestationRow {
  employment_id: number
  full_name: string | null
  attestation_date: string | null
}

export interface AttestationQueryParams {
  page?: number
  per_page?: number
  q?: string
  sort?: string
  direction?: 'asc' | 'desc'
  [key: string]: string | number | boolean | undefined
}

interface ApiResponse<T> {
  success: boolean
  message?: string
  data?: T
}

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  }
  const csrfToken = getCsrfToken()
  if (csrfToken && options.method && options.method !== 'GET') {
    headers['X-CSRF-Token'] = csrfToken
  }

  const response = await fetch(url, {
    credentials: 'include',
    headers,
    ...options,
  })
  const payload = (await response.json()) as ApiResponse<T>
  if (!response.ok || !payload.success) {
    throw new ApiError(localizeApiMessage(payload.message), response.status, payload.message)
  }
  return payload.data as T
}

export const attestationApi = {
  list: (params: AttestationQueryParams = {}) =>
    request<Paginated<AttestationRow>>(`/api/attestations${buildQuery(params)}`),
  update: (employmentId: number, attestationDate: string | null) =>
    request<AttestationRow>(`/api/attestations/${employmentId}`, {
      method: 'PATCH',
      body: JSON.stringify({ attestation_date: attestationDate }),
    }),
}
