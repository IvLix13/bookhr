import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import AttentionPanel from '@/components/AttentionPanel.vue'

vi.mock('@/api/client', () => ({
  api: {
    attention: vi.fn(async () => ({
      total: 2,
      counts: { events: 1, contracts: 1 },
      items: [
        {
          category: 'events',
          id: 42,
          title: 'Просроченное мероприятие',
          subtitle: 'Иван Иванов',
          due_date: '2026-07-01',
          severity: 'danger',
          route: '/events',
        },
        {
          category: 'grades',
          id: 88,
          title: 'Рассмотреть повышение грейда',
          subtitle: 'Иван Иванов',
          due_date: '2026-07-10',
          severity: 'warning',
          route: '/?event=88',
        },
        {
          category: 'contracts',
          id: 7,
          title: 'Истекает договор',
          severity: 'warning',
          route: '/contracts',
        },
      ],
    })),
  },
}))

async function mountPanel() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'calendar', component: { template: '<div />' } },
      { path: '/events', name: 'events', component: { template: '<div />' } },
      { path: '/contracts', name: 'contracts', component: { template: '<div />' } },
    ],
  })
  await router.push({ name: 'calendar' })
  await router.isReady()
  const replaceSpy = vi.spyOn(router, 'replace')

  const wrapper = mount(AttentionPanel, {
    global: {
      plugins: [router],
    },
  })
  await flushPromises()
  return { wrapper, replaceSpy }
}

describe('AttentionPanel', () => {
  it('opens an event on the calendar instead of navigating to events', async () => {
    const { wrapper, replaceSpy } = await mountPanel()

    const eventButton = wrapper.findAll('button.attention-link')[0]
    expect(eventButton.exists()).toBe(true)
    expect(eventButton.text()).toContain('Просроченное мероприятие')

    await eventButton.trigger('click')

    expect(replaceSpy).toHaveBeenCalledWith({ name: 'calendar', query: { event: '42' } })
    expect(wrapper.find('a.attention-link').attributes('href')).not.toContain('/events')
  })

  it('opens a grade-related item on the calendar instead of navigating to grades', async () => {
    const { wrapper, replaceSpy } = await mountPanel()

    const gradeButton = wrapper
      .findAll('button.attention-link')
      .find((button) => button.text().includes('Рассмотреть повышение грейда'))
    expect(gradeButton).toBeTruthy()

    await gradeButton!.trigger('click')

    expect(replaceSpy).toHaveBeenCalledWith({ name: 'calendar', query: { event: '88' } })
    expect(wrapper.html()).not.toContain('/grades')
  })
})
