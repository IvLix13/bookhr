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

  it('shows contract expiry from a later page on the correct day', async () => {
    const expiry = makeEvent({
      id: 201,
      title: 'Договор до…: Иван Иванов',
      event_type: 'contract',
      source: 'rule',
      reference_type: 'contract',
      reference_id: 15,
    })
    events.mockResolvedValueOnce({ items: [], page: 1, pages: 2 })
    events.mockResolvedValueOnce({ items: [expiry], page: 2, pages: 2 })

    const wrapper = await mountView()
    expect(wrapper.getComponent(MonthCalendar).props('events')).toEqual([expiry])
    expect(events).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, per_page: 200 }))
    const day = wrapper.findAll('.day-button').find((button) => button.text().includes(expiry.title))!
    expect(day.text()).toContain(String(new Date().getDate()))
    await day.trigger('click')
    expect(wrapper.getComponent({ name: 'DayEventsModal' }).props('date')).toBe(expiry.event_date)
    wrapper.unmount()
  })

  it('shows both attestation events and hides an explicitly cancelled one', async () => {
    events.mockResolvedValue({ items: [
      makeEvent({ id: 1, event_type: 'attestation', title: 'Проведение аттестации', source: 'rule' }),
      makeEvent({ id: 2, event_type: 'attestation_preparation', title: 'Подготовка документов для аттестации', source: 'rule' }),
      makeEvent({ id: 3, event_type: 'attestation', title: 'Отменённая аттестация', status: 'cancelled', source: 'rule' }),
    ], total: 3, page: 1, per_page: 200, pages: 1 })
    const wrapper = await mountView()
    expect((wrapper.getComponent(MonthCalendar).props('events') as EventItem[]).map((event) => event.id)).toEqual([1, 2])
    expect(wrapper.text()).toContain('Проведение аттестации')
    expect(wrapper.text()).toContain('Подготовка документов для аттестации')
    expect(wrapper.text()).not.toContain('Отменённая аттестация')
    wrapper.unmount()
  })
})
