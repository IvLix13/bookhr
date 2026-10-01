import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import { useAuthStore } from '@/stores/auth'
import { defaultAppRoute, postLoginNavigation } from '@/router/access'

describe('router access helpers', () => {
  it('uses calendar for editors and employees for viewer', () => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'hr', full_name: 'HR', role: 'hr' }
    expect(defaultAppRoute(auth)).toEqual({ name: 'calendar' })

    auth.user = { id: 2, username: 'viewer', full_name: 'Viewer', role: 'viewer' }
    expect(defaultAppRoute(auth)).toEqual({ name: 'employees' })
  })

  it('does not send viewer to calendar root after login', () => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = { id: 2, username: 'viewer', full_name: 'Viewer', role: 'viewer' }

    expect(postLoginNavigation(auth, undefined)).toEqual({ name: 'employees' })
    expect(postLoginNavigation(auth, '/')).toEqual({ name: 'employees' })
    expect(postLoginNavigation(auth, '/contracts')).toBe('/contracts')
  })
})
