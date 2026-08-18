import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import DayEventsModal from '@/components/DayEventsModal.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/api/client', () => ({
  api: {
    events: vi.fn(async () => ({
      items: [
        {
          id: 1,
          title: 'Event',
          event_type: 'manual',
          description: null,
          event_date: '2026-07-24',
          status: 'planned',
          effective_status: 'planned',
          source: 'manual',
          employment_id: null,
          employee_name: null,
          created_by: null,
          created_at: null,
          completed_at: null,
          completion_comment: null,
        },
      ],
    })),
    getEvent: vi.fn(async () => ({
      id: 1,
      title: 'Event',
      event_type: 'manual',
      description: null,
      event_date: '2026-07-24',
      status: 'planned',
      effective_status: 'planned',
      source: 'manual',
      employment_id: null,
      employee_name: null,
      created_by: null,
      created_at: null,
      completed_at: null,
      completion_comment: null,
    })),
    completeEvent: vi.fn(async () => ({})),
    cancelEvent: vi.fn(),
    reopenEvent: vi.fn(),
    updateEvent: vi.fn(),
    deleteEvent: vi.fn(),
    createEvent: vi.fn(async () => ({})),
    employees: vi.fn(async () => ({ items: [] })),
  },
}))

describe('DayEventsModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.body.innerHTML = ''
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('hides complete action for viewer', async () => {
    const auth = useAuthStore()
    auth.user = {
      id: 1,
      username: 'viewer',
      full_name: 'Viewer',
      role: 'viewer',
    }

    mount(DayEventsModal, {
      props: {
        open: true,
        date: '2026-07-24',
      },
      attachTo: document.body,
    })

    await flushPromises()

    expect(document.body.querySelector('button.secondary')).toBeNull()
  })

  it('shows complete action for hr', async () => {
    const auth = useAuthStore()
    auth.user = {
      id: 2,
      username: 'hr',
      full_name: 'HR',
      role: 'hr',
    }

    mount(DayEventsModal, {
      props: {
        open: true,
        date: '2026-07-24',
      },
      attachTo: document.body,
      global: {
        stubs: {
          teleport: true,
          EventDetailModal: true,
        },
      },
    })

    await flushPromises()

    expect(document.body.querySelector('.item-button')).not.toBeNull()
  })
})
