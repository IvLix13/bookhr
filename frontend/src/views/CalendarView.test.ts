import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import MonthCalendar from '@/components/MonthCalendar.vue'
import type { EventItem } from '@/types'
import { formatLocalDate } from '@/utils/dates'
import CalendarView from '@/views/CalendarView.vue'

function makeEvent(overrides: Partial<EventItem> = {}): EventItem {
  return {
    id: 1,
    title: 'Открытое',
    event_type: 'manual',
    description: null,
    event_date: formatLocalDate(new Date()),
    status: 'planned',
    effective_status: 'planned',
    source: 'manual',
    employment_id: null,
    employee_name: null,
    created_by: null,
    created_at: null,
    completed_at: null,
    completion_comment: null,
    ...overrides,
  }
}

const { events, upcomingEvents } = vi.hoisted(() => ({
  events: vi.fn(),
  upcomingEvents: vi.fn(async () => []),
}))

vi.mock('@/api/client', () => ({
  api: {
    events,
    upcomingEvents,
    attention: vi.fn(async () => ({ total: 0, counts: {}, items: [] })),
  },
}))

describe('CalendarView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    events.mockReset()
    upcomingEvents.mockReset()
    upcomingEvents.mockResolvedValue([])
  })

  async function mountView() {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/calendar', name: 'calendar', component: { template: '<div />' } }],
    })
    await router.push({ name: 'calendar' })
    await router.isReady()
    const wrapper = mount(CalendarView, {
      global: {
        plugins: [router],
        stubs: {
          CalendarFeedPanel: true,
          DayEventsModal: true,
          EventDetailModal: true,
        },
      },
    })
    await flushPromises()
    return wrapper
  }

  it('does not pass cancelled events to the month calendar', async () => {
    events.mockResolvedValue({
      items: [
        makeEvent({ id: 1, title: 'Открытое', status: 'planned' }),
        makeEvent({
          id: 2,
          title: 'Отменённое',
          status: 'cancelled',
          effective_status: 'cancelled',
        }),
        makeEvent({
          id: 3,
          title: 'Выполненное',
          status: 'completed',
          effective_status: 'completed',
        }),
      ],
      total: 3,
      page: 1,
      per_page: 200,
      pages: 1,
    })

    const wrapper = await mountView()
    const calendar = wrapper.getComponent(MonthCalendar)
    const visible = calendar.props('events') as EventItem[]

    expect(visible.map((item) => item.id)).toEqual([1, 3])
    expect(wrapper.text()).toContain('Открытое')
    expect(wrapper.text()).toContain('Выполненное')
    expect(wrapper.text()).not.toContain('Отменённое')
  })
})
