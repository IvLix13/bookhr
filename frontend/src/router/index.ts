import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
    {
      path: '/',
      component: () => import('@/layouts/AppShell.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: '', name: 'calendar', component: () => import('@/views/CalendarView.vue') },
        { path: 'statistics', name: 'statistics', component: () => import('@/views/StatisticsView.vue') },
        { path: 'employees', name: 'employees', component: () => import('@/views/EmployeesView.vue') },
        {
          path: 'import',
          component: () => import('@/views/import/ImportLayout.vue'),
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
        { path: 'events/create', name: 'event-create', component: () => import('@/views/EventCreateView.vue') },
        { path: 'contracts', name: 'contracts', component: () => import('@/views/ContractsView.vue') },
        { path: 'grades', name: 'grades', component: () => import('@/views/GradesView.vue') },
        { path: 'rewards', name: 'rewards', component: () => import('@/views/RewardsView.vue') },
        { path: 'awards', name: 'awards', component: () => import('@/views/AwardsView.vue') },
        { path: 'passports', name: 'passports', component: () => import('@/views/PassportsView.vue') },
        { path: 'events', name: 'events', component: () => import('@/views/EventsView.vue') },
        { path: 'grade-catalog', name: 'grade-catalog', component: () => import('@/views/GradeCatalogView.vue') },
        {
          path: 'settings',
          component: () => import('@/views/settings/SettingsLayout.vue'),
          meta: { requiresAdmin: true },
          children: [
            { path: '', redirect: { name: 'settings-users' } },
            {
              path: 'users',
              name: 'settings-users',
              component: () => import('@/views/settings/SettingsUsersTab.vue'),
            },
            {
              path: 'notifications',
              name: 'settings-notifications',
              component: () => import('@/views/settings/SettingsNotificationsTab.vue'),
            },
          ],
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.user && to.meta.requiresAuth) {
    await auth.fetchMe()
  }
  if (to.meta.requiresAuth && !auth.user) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && auth.user) {
    return { name: 'calendar' }
  }
  if (to.matched.some((record) => record.meta.requiresAdmin) && !auth.isAdmin()) {
    return { name: 'calendar' }
  }
})

export default router
