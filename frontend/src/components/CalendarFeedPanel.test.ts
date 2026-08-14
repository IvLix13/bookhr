import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import CalendarFeedPanel from '@/components/CalendarFeedPanel.vue'
import type { EventItem } from '@/types'

vi.mock('@/api/client', () => ({
  api: {
    attention: vi.fn(async () => ({
      total: 0,
      counts: {},
      items: [],
    })),
  },
}))

const sampleEvents: EventItem[] = [
  {
    id: 1,
    title: 'Test event',
    event_type: 'manual',
    description: null,
    event_date: '2026-07-24',
    status: 'planned',
    source: 'manual',
    employment_id: null,
    employee_name: 'Alice',
    created_by: null,
    created_at: null,
    completed_at: null,
    completion_comment: null,
  },
]

describe('CalendarFeedPanel', () => {
  it('switches between attention and upcoming panels', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'calendar', component: { template: '<div />' } },
        { path: '/events', name: 'events', component: { template: '<div />' } },
      ],
    })
    await router.push({ name: 'calendar' })
    await router.isReady()

    const wrapper = mount(CalendarFeedPanel, {
      props: {
        events: sampleEvents,
      },
      global: {
        plugins: [router],
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
          },
          EventDetailModal: true,
        },
      },
    })

    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs).toHaveLength(2)
    expect(tabs[0].attributes('aria-selected')).toBe('true')
    expect(wrapper.find('#feed-panel-attention').attributes('hidden')).toBeUndefined()
    expect(wrapper.find('#feed-panel-upcoming').attributes('hidden')).toBeDefined()

    await tabs[1].trigger('click')

    expect(tabs[1].attributes('aria-selected')).toBe('true')
    expect(wrapper.find('#feed-panel-attention').attributes('hidden')).toBeDefined()
    expect(wrapper.find('#feed-panel-upcoming').attributes('hidden')).toBeUndefined()
    expect(wrapper.text()).toContain('Test event')
  })
})
