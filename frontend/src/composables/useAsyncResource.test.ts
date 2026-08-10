import { describe, expect, it, vi } from 'vitest'
import { useAsyncResource } from '@/composables/useAsyncResource'
import { ApiError } from '@/api/errors'

describe('useAsyncResource', () => {
  it('loads data successfully', async () => {
    const resource = useAsyncResource<string>()
    await resource.execute(async () => 'ok')
    expect(resource.data.value).toBe('ok')
    expect(resource.status.value).toBe('success')
    expect(resource.error.value).toBe('')
  })

  it('captures errors and supports retry', async () => {
    const resource = useAsyncResource<string>()
    const fn = vi
      .fn()
      .mockRejectedValueOnce(new ApiError('fail', 500))
      .mockResolvedValueOnce('recovered')

    await expect(resource.execute(fn)).rejects.toThrow('fail')
    expect(resource.error.value).toBe('fail')
    expect(resource.data.value).toBeNull()

    await resource.retry(fn)
    expect(resource.data.value).toBe('recovered')
    expect(resource.error.value).toBe('')
  })

  it('uses refreshing state when data already exists', async () => {
    const resource = useAsyncResource<number>()
    await resource.execute(async () => 1)

    let refreshingDuringLoad = false
    const promise = resource.execute(async () => {
      refreshingDuringLoad = resource.isRefreshing()
      return 2
    }, { keepData: true })

    expect(resource.isRefreshing()).toBe(true)
    await promise
    expect(refreshingDuringLoad).toBe(true)
    expect(resource.data.value).toBe(2)
  })
})
