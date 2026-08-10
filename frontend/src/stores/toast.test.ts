import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useToastStore } from '@/stores/toast'

describe('toast store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  it('queues messages and deduplicates', () => {
    const store = useToastStore()
    store.success('Saved')
    store.success('Saved')
    expect(store.items).toHaveLength(1)
  })

  it('auto dismisses items', () => {
    const store = useToastStore()
    store.push('Hello', 'info', 1000)
    expect(store.items).toHaveLength(1)
    vi.advanceTimersByTime(1000)
    expect(store.items).toHaveLength(0)
  })
})
