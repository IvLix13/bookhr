import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useUiStore } from '@/stores/ui'

describe('ui store', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('toggles sidebar expanded state', () => {
    const store = useUiStore()
    expect(store.sidebarExpanded).toBe(false)
    store.toggleSidebar()
    expect(store.sidebarExpanded).toBe(true)
  })
})
