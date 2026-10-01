import { createRouter, createWebHistory } from 'vue-router'
import { setUnauthorizedHandler } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

function defaultAppRoute(auth: ReturnType<typeof useAuthStore>) {
  return auth.canEdit() ? { name: 'calendar' as const } : { name: 'employees' as const }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
    {
      path: '/',
      component: () => import('@/layouts/AppShell.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: 'onboarding', name: 'onboarding', component: () => import('@/views/OnboardingView.vue') },
        {
          path: '',
          name: 'calendar',
          component: () => import('@/views/CalendarView.vue'),
          meta: { requiresEdit: true },
        },
        {
          path: 'events',
          name: 'events',
          component: () => import('@/views/EventsView.vue'),
          meta: { requiresEdit: true },
        },
        {
          path: 'events/create',
          redirect: { name: 'events', query: { create: '1' } },
          meta: { requiresEdit: true },
        },
        { path: 'employees', name: 'employees', component: () => import('@/views/EmployeesView.vue') },
        { path: 'contracts', name: 'contracts', component: () => import('@/views/ContractsView.vue') },
        {
          path: 'grades',
          name: 'grades',
          component: () => import('@/views/GradesView.vue'),
          meta: { requiresEdit: true },
        },
        { path: 'attestations', name: 'attestations', component: () => import('@/views/AttestationsView.vue') },
        {
          path: 'rewards',
          name: 'rewards',
          component: () => import('@/views/RewardsView.vue'),
          meta: { requiresEdit: true },
        },
        {
          path: 'awards',
          name: 'awards',
          component: () => import('@/views/AwardsView.vue'),
          meta: { requiresEdit: true },
        },
        { path: 'passports', name: 'passports', component: () => import('@/views/PassportsView.vue') },
        {
          path: 'import',
          component: () => import('@/views/import/ImportLayout.vue'),
          meta: { requiresEdit: true },
          children: [
            { path: '', redirect: { name: 'import-employees' } },
            {
              path: 'employees',
              name: 'import-employees',
              component: () => import('@/views/import/ImportEmployeesTab.vue'),
            },
            {
              path: 'rewards',
              name: 'import-rewards',
              component: () => import('@/views/import/ImportRewardsTab.vue'),
            },
          ],
        },
        {
          path: 'statistics',
          name: 'statistics',
          component: () => import('@/views/StatisticsView.vue'),
          meta: { requiresEdit: true },
        },
        {
          path: 'grade-catalog',
          name: 'grade-catalog',
          component: () => import('@/views/GradeCatalogView.vue'),
          meta: { requiresEdit: true },
        },
        {
          path: 'settings',
          component: () => import('@/views/settings/SettingsLayout.vue'),
          children: [
            { path: '', redirect: { name: 'settings-users' } },
            {
              path: 'users',
              name: 'settings-users',
              component: () => import('@/views/settings/SettingsUsersTab.vue'),
              meta: { requiresAdmin: true },
            },
            {
              path: 'notifications',
              name: 'settings-notifications',
              component: () => import('@/views/settings/SettingsNotificationsTab.vue'),
              meta: { requiresEdit: true },
            },
          ],
        },
      ],
    },
  ],
})

setUnauthorizedHandler(() => {
  const auth = useAuthStore()
  if (!auth.user) return
  auth.clearSession()
  const toast = useToast()
  toast.error('Сессия истекла. Войдите снова.')
  void router.replace({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.user && to.meta.requiresAuth) {
    await auth.ensureCsrf()
    await auth.fetchMe()
  }
  if (to.meta.requiresAuth && !auth.user) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && auth.user) {
    return defaultAppRoute(auth)
  }
  if (to.matched.some((record) => record.meta.requiresAdmin) && !auth.isAdmin()) {
    return { ...defaultAppRoute(auth), query: { denied: 'admin' } }
  }
  if (to.matched.some((record) => record.meta.requiresEdit) && !auth.canEdit()) {
    return { ...defaultAppRoute(auth), query: { denied: 'edit' } }
  }
})

export default router
