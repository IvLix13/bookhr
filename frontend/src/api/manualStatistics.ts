import { ApiError } from '@/api/errors'
import { getCsrfToken } from '@/api/client'
import type { ApiResponse } from '@/types'
import type { ManualStatisticsData } from '@/types/manualStatistics'
import { localizeApiMessage } from '@/utils/labels'

async function parsePayload<T>(response: Response): Promise<ApiResponse<T>> {
  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) {
    throw new ApiError('Некорректный ответ сервера', response.status)
  }
  return (await response.json()) as ApiResponse<T>
}

async function requestManualStatistics(
  url: string,
  options: RequestInit = {},
): Promise<ManualStatisticsData> {
  const response = await fetch(url, {
    credentials: 'include',
    ...options,
  })
  const payload = await parsePayload<ManualStatisticsData>(response)
  if (!response.ok || !payload.success) {
    throw new ApiError(localizeApiMessage(payload.message), response.status, payload.message)
  }
  return payload.data as ManualStatisticsData
}

export const manualStatisticsApi = {
  get: () => requestManualStatistics('/api/stats/manual'),

  upload: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    const csrfToken = getCsrfToken()
    return requestManualStatistics('/api/stats/manual/upload', {
      method: 'POST',
      headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : {},
      body: form,
    })
  },

  downloadTemplate: async () => {
    const response = await fetch('/api/stats/manual/template', {
      credentials: 'include',
    })
    if (!response.ok) {
      let message = 'Не удалось скачать шаблон'
      try {
        const payload = await parsePayload<unknown>(response)
        message = localizeApiMessage(payload.message) ?? message
      } catch {
        // Keep the generic download error for non-JSON responses.
      }
      throw new ApiError(message, response.status)
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'manual_statistics_template.xlsx'
    link.click()
    URL.revokeObjectURL(url)
  },
}
