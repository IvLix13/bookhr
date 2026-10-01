import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { User } from '@/types'
import { useAuthStore } from '@/stores/auth'

const { me, fetchCsrf } = vi.hoisted(() => ({
  me: vi.fn(),
  fetchCsrf: vi.fn(async () => undefined),
}))

vi.mock('@/api/client', () => ({
  api: {
    me,
    fetchCsrf,
  },
  setUnauthorizedHandler: vi.fn(),
  setCsrfToken: vi.fn(),
}))

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ error: vi.fn() }),
}))

const viewerUser: User = {
  id: 2,
  username: 'viewer',
  full_name: 'Viewer',
  role: 'viewer',
}

const hrUser: User = {
  id: 3,
  username: 'hr',
  full_name: 'HR',
  role: 'hr',
}

describe('router access guards', () => {
  beforeEach(async () => {
    vi.resetModules()
    setActivePinia(createPinia())
    me.mockReset()
    fetchCsrf.mockClear()
  })

  async function loadRouter() {
    const { default: router } = await import('@/router/index')
    return router
  }

  it('redirects viewer away from restricted routes', async () => {
    const router = await loadRouter()
    const auth = useAuthStore()
    auth.user = viewerUser

    const restricted = [
      '/rewards',
      '/awards',
      '/statistics',
      '/import',
      '/import/employees',
      '/import/rewards',
    ] as const

    for (const path of restricted) {
      await router.push(path)
      await router.isReady()
      expect(router.currentRoute.value.name).toBe('calendar')
      expect(router.currentRoute.value.query.denied).toBe('edit')
    }
  })

  it('allows hr into restricted routes', async () => {
    const router = await loadRouter()
    const auth = useAuthStore()
    auth.user = hrUser

    await router.push('/rewards')
    await router.isReady()
    expect(router.currentRoute.value.name).toBe('rewards')
    expect(router.currentRoute.value.query.denied).toBeUndefined()
  })

  it('restores viewer via fetchMe before enforcing edit routes', async () => {
    const router = await loadRouter()
    const auth = useAuthStore()
    auth.user = null
    me.mockResolvedValue(viewerUser)

    await router.push('/statistics')
    await router.isReady()

    expect(me).toHaveBeenCalled()
    expect(router.currentRoute.value.name).toBe('calendar')
    expect(router.currentRoute.value.query.denied).toBe('edit')
  })
})
