import type { RouteLocationRaw } from 'vue-router'
import type { useAuthStore } from '@/stores/auth'

export type AuthStore = ReturnType<typeof useAuthStore>

/** First screen after auth for the current role. Must not use `requiresEdit`. */
export function defaultAppRoute(auth: AuthStore): RouteLocationRaw {
  return auth.canEdit() ? { name: 'calendar' } : { name: 'employees' }
}

function isSafeRedirectPath(target: string | undefined): target is string {
  return Boolean(target && target.startsWith('/') && !target.startsWith('//'))
}

/** Post-login navigation: never send viewer to `/` (calendar) by default. */
export function postLoginNavigation(
  auth: AuthStore,
  redirect: string | undefined,
): RouteLocationRaw | string {
  if (!isSafeRedirectPath(redirect)) {
    return defaultAppRoute(auth)
  }
  if (!auth.canEdit() && (redirect === '/' || redirect === '')) {
    return defaultAppRoute(auth)
  }
  return redirect
}
