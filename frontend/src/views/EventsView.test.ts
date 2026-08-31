import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EventsView from '@/views/EventsView.vue'
import { useAuthStore } from '@/stores/auth'
import type { EventItem } from '@/types'

const sampleEvent: EventItem = {
  id: 42,
  title: 'Event 42',
  event_type: 'manual',
  description: null,
  event_date: '2026-07-24',
  status: 'planned',
  effective_status: 'planned',
  source: 'manual',
  employment_id: null,
  employee_name: 'Тестов',
  created_by: null,
  created_at: null,
  completed_at: null,
  completion_comment: null,
}

const routeState = vi.hoisted(() => ({
  query: {} as Record<string, string>,
}))

const replace = vi.hoisted(() => vi.fn(async (location: { query?: Record<string, string> }) => {
  routeState.query = { ...(location.query ?? {}) }
}))

const { events, getEvent, completeEvent, employees, createEvent } = vi.hoisted(() => ({
  events: vi.fn(async () => ({
    items: [sampleEvent],
    total: 1,
    page: 1,
    per_page: 25,
    pages: 1,
  })),
  getEvent: vi.fn(async () => sampleEvent),
  completeEvent: vi.fn(async () => sampleEvent),
  employees: vi.fn(async () => ({
    items: [],
    total: 0,
    page: 1,
    per_page: 200,
    pages: 0,
  })),
  createEvent: vi.fn(async () => ({})),
}))

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return {
    ...actual,
    useRoute: () => ({
      get query() {
        return routeState.query
      },
    }),
    useRouter: () => ({
      replace,
    }),
  }
})

vi.mock('@/api/client', () => ({
  api: {
    events,
    getEvent,
    completeEvent,
    cancelEvent: vi.fn(),
    reopenEvent: vi.fn(),
    updateEvent: vi.fn(),
    deleteEvent: vi.fn(),
    employees,
    createEvent,
  },
}))

describe('EventsView event modal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    routeState.query = {}
    replace.mockClear()
    events.mockClear()
    getEvent.mockClear()
    completeEvent.mockClear()
    employees.mockClear()
    createEvent.mockClear()
    document.body.innerHTML = ''
  })

  async function mountView(role: 'admin' | 'hr' | 'viewer' = 'hr') {
    const auth = useAuthStore()
    auth.user = {
      id: 1,
      username: role,
      full_name: role,
      role,
    }
    const wrapper = mount(EventsView, {
      attachTo: document.body,
      global: {
        stubs: {
          teleport: true,
        },
      },
    })
    await flushPromises()
    return wrapper
  }

  it('opens detail modal from event query', async () => {
    routeState.query = { event: '42' }
    await mountView()
    await flushPromises()
    expect(getEvent).toHaveBeenCalledWith(42)
    expect(document.body.textContent).toContain('Event 42')
  })

  it('sets event query on row click', async () => {
    const wrapper = await mountView()
    await wrapper.get('.data-table-row').trigger('click')
    expect(replace).toHaveBeenCalledWith({
      query: { event: '42' },
    })
  })

  it('keeps complete shortcut without opening modal via stop', async () => {
    const wrapper = await mountView()
    await wrapper.get('.data-table-row .btn.secondary').trigger('click')
    await flushPromises()
    expect(completeEvent).toHaveBeenCalledWith(42)
    expect(replace).not.toHaveBeenCalled()
  })

  it('opens details instead of quick-completing a blocked grade event', async () => {
    events.mockResolvedValueOnce({
      items: [
        {
          ...sampleEvent,
          event_type: 'grade',
          grade_completion: {
            next_rank: 2,
            candidates: [],
            requires_selection: false,
            eligible_date: null,
            blocked_reason: 'Укажите наличие высшего образования у сотрудника',
          },
        },
      ],
      total: 1,
      page: 1,
      per_page: 25,
      pages: 1,
    })
    const wrapper = await mountView()
    await wrapper.get('.data-table-row .btn.secondary').trigger('click')

    expect(completeEvent).not.toHaveBeenCalled()
    expect(replace).toHaveBeenCalledWith({ query: { event: '42' } })
  })

  it('shows create button for editors and opens create query', async () => {
    const wrapper = await mountView('hr')
    const button = wrapper.get('header .btn')
    expect(button.text()).toBe('Создать мероприятие')
    await button.trigger('click')
    expect(replace).toHaveBeenCalledWith({
      query: { create: '1' },
    })
  })

  it('hides create button for viewers', async () => {
    const wrapper = await mountView('viewer')
    expect(wrapper.find('header .btn').exists()).toBe(false)
  })

  it('requests nearest date sort by default', async () => {
    await mountView('hr')
    expect(events).toHaveBeenCalledWith(
      expect.objectContaining({
        sort: 'nearest_date',
        direction: 'asc',
      }),
    )
  })

  it('opens create form from create query', async () => {
    routeState.query = { create: '1' }
    await mountView('hr')
    await flushPromises()
    expect(employees).toHaveBeenCalled()
    expect(document.body.textContent).toContain('Создать мероприятие')
    expect(document.body.textContent).toContain('Название')
  })
})
