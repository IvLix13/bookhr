import { ref, type Ref } from 'vue'
import { normalizeError } from '@/api/errors'

export type AsyncStatus = 'idle' | 'loading' | 'refreshing' | 'success' | 'error'

export function useAsyncResource<T>() {
  const data = ref<T | null>(null) as Ref<T | null>
  const status = ref<AsyncStatus>('idle')
  const error = ref('')
  let requestId = 0

  async function execute(fn: () => Promise<T>, options?: { keepData?: boolean }) {
    const currentId = ++requestId
    const keepData = options?.keepData ?? data.value != null
    status.value = keepData ? 'refreshing' : 'loading'
    error.value = ''

    try {
      const result = await fn()
      if (currentId !== requestId) return
      data.value = result
      status.value = 'success'
      return result
    } catch (err) {
      if (currentId !== requestId) return
      error.value = normalizeError(err)
      status.value = 'error'
      if (!keepData) data.value = null
      throw err
    }
  }

  function retry(fn: () => Promise<T>, options?: { keepData?: boolean }) {
    return execute(fn, options)
  }

  function reset() {
    requestId += 1
    data.value = null
    status.value = 'idle'
    error.value = ''
  }

  const isLoading = () => status.value === 'loading'
  const isRefreshing = () => status.value === 'refreshing'
  const isBusy = () => status.value === 'loading' || status.value === 'refreshing'

  return {
    data,
    status,
    error,
    execute,
    retry,
    reset,
    isLoading,
    isRefreshing,
    isBusy,
  }
}
