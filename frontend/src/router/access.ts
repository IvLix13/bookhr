import type { RouteLocationRaw, RouteLocationAsRelativeGeneric } from 'vue-router'
import type { useAuthStore } from '@/stores/auth'

export type AuthStore = ReturnType<typeof useAuthStore>

/** First screen after auth for the current role. Must not use `requiresEdit`. */
export function defaultAppRoute(auth: AuthStore): RouteLocationAsRelativeGeneric {
  return auth.canEdit() ? { name: 'calendar' } : { name: 'employees' }
}

function isSafeRedirectPath(target: string | undefined): target is string {
  return Boolean(target && target.startsWith('/') && !target.startsWith('//'))
}

/** Post-login navigation: preserve explicit calendar redirects for viewer. */
export function postLoginNavigation(
  auth: AuthStore,
  redirect: string | undefined,
): RouteLocationRaw | string {
  if (!isSafeRedirectPath(redirect)) {
    return defaultAppRoute(auth)
  }
  return redirect
}
