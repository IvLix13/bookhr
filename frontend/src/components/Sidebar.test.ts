import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'
import Sidebar from '@/components/Sidebar.vue'
import { useAuthStore } from '@/stores/auth'
import { MODULE_LABELS } from '@/utils/labels'

const routes = [
  { path: '/', name: 'calendar', component: { template: '<div />' } },
  { path: '/events', name: 'events', component: { template: '<div />' } },
  { path: '/employees', name: 'employees', component: { template: '<div />' } },
  { path: '/contracts', name: 'contracts', component: { template: '<div />' } },
  { path: '/grades', name: 'grades', component: { template: '<div />' } },
  { path: '/rewards', name: 'rewards', component: { template: '<div />' } },
  { path: '/awards', name: 'awards', component: { template: '<div />' } },
  { path: '/passports', name: 'passports', component: { template: '<div />' } },
  { path: '/import/employees', name: 'import-employees', component: { template: '<div />' } },
  { path: '/statistics', name: 'statistics', component: { template: '<div />' } },
  { path: '/settings/users', name: 'settings-users', component: { template: '<div />' } },
]

describe('Sidebar navigation order', () => {
  async function mountSidebar(role: 'admin' | 'hr' = 'admin') {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = {
      id: 1,
      username: role,
      full_name: role,
      role,
    }
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    await router.push('/')
    await router.isReady()
    return mount(Sidebar, {
      props: { expanded: true },
      global: { plugins: [router] },
    })
  }

  it('renders items in the requested order for admin', async () => {
    const wrapper = await mountSidebar('admin')
    const labels = wrapper.findAll('.nav-label').map((item) => item.text())
    expect(labels).toEqual([
      MODULE_LABELS.calendar,
      MODULE_LABELS.events,
      MODULE_LABELS.employees,
      MODULE_LABELS.contracts,
      MODULE_LABELS.grades,
      MODULE_LABELS.rewards,
      MODULE_LABELS.awards,
      MODULE_LABELS.passports,
      MODULE_LABELS.import,
      MODULE_LABELS.statistics,
      MODULE_LABELS.settings,
    ])
  })

  it('does not keep a dedicated create-event item', async () => {
    const wrapper = await mountSidebar('admin')
    expect(wrapper.text()).not.toContain(MODULE_LABELS.eventCreate)
  })
})
