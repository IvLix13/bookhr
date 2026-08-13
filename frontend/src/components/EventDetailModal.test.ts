import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import EventDetailModal from '@/components/EventDetailModal.vue'
import { useAuthStore } from '@/stores/auth'
import type { EventItem } from '@/types'

const plannedEvent: EventItem = {
  id: 7,
  title: 'Подготовить рапорт',
  event_type: 'report',
  description: 'Описание',
  event_date: '2026-07-24',
  status: 'planned',
  effective_status: 'planned',
  source: 'rule',
  employment_id: 1,
  employee_name: 'Иванов Иван',
  created_by: 'Система',
  created_at: '2026-07-01T10:00:00',
  completed_at: null,
  completion_comment: null,
}

const completedEvent: EventItem = {
  ...plannedEvent,
  status: 'completed',
  effective_status: 'completed',
  completed_at: '2026-07-20T12:00:00',
  completion_comment: 'Готово',
}

const { getEvent, completeEvent, cancelEvent, reopenEvent } = vi.hoisted(() => ({
  getEvent: vi.fn(async () => plannedEvent),
  completeEvent: vi.fn(async () => ({ ...plannedEvent, status: 'completed' })),
  cancelEvent: vi.fn(async () => ({ ...plannedEvent, status: 'cancelled' })),
  reopenEvent: vi.fn(async () => plannedEvent),
}))

vi.mock('@/api/client', () => ({
  api: {
    getEvent,
    completeEvent,
    cancelEvent,
    reopenEvent,
  },
}))

describe('EventDetailModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.body.innerHTML = ''
    getEvent.mockReset()
    completeEvent.mockReset()
    cancelEvent.mockReset()
    reopenEvent.mockReset()
    getEvent.mockResolvedValue(plannedEvent)
    completeEvent.mockResolvedValue({ ...plannedEvent, status: 'completed' })
    cancelEvent.mockResolvedValue({ ...plannedEvent, status: 'cancelled' })
    reopenEvent.mockResolvedValue(plannedEvent)
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  async function mountModal(role: 'admin' | 'hr' | 'viewer' = 'hr') {
    const auth = useAuthStore()
    auth.user = {
      id: 1,
      username: role,
      full_name: role,
      role,
    }
    const wrapper = mount(EventDetailModal, {
      props: {
        open: true,
        eventId: 7,
      },
      attachTo: document.body,
    })
    await flushPromises()
    return wrapper
  }

  it('renders event details', async () => {
    await mountModal('hr')
    expect(document.body.textContent).toContain('Подготовить рапорт')
    expect(document.body.textContent).toContain('Иванов Иван')
    expect(document.body.textContent).toContain('Описание')
    expect(getEvent).toHaveBeenCalledWith(7)
  })

  it('hides actions for viewer', async () => {
    await mountModal('viewer')
    const text = document.body.textContent ?? ''
    expect(text).toContain('Подготовить рапорт')
    expect(text).not.toContain('Выполнить')
    expect(text).not.toContain('Отменить')
    expect(text).not.toContain('Переоткрыть')
  })

  it('shows complete and cancel for open events', async () => {
    await mountModal('hr')
    const text = document.body.textContent ?? ''
    expect(text).toContain('Выполнить')
    expect(text).toContain('Отменить')
    expect(text).not.toContain('Переоткрыть')
  })

  it('completes event and emits changed', async () => {
    const wrapper = await mountModal('hr')
    const buttons = Array.from(document.body.querySelectorAll('button'))
    const completeBtn = buttons.find((button) => button.textContent?.includes('Выполнить'))
    expect(completeBtn).toBeTruthy()
    await completeBtn!.click()
    await flushPromises()
    expect(completeEvent).toHaveBeenCalledWith(7, undefined)
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('shows reopen for completed events', async () => {
    getEvent.mockResolvedValueOnce(completedEvent)
    await mountModal('hr')
    const text = document.body.textContent ?? ''
    expect(text).toContain('Переоткрыть')
    expect(text).not.toContain('Выполнить')
    expect(text).toContain('Готово')

    const reopenBtn = Array.from(document.body.querySelectorAll('button')).find((button) =>
      button.textContent?.includes('Переоткрыть'),
    )
    expect(reopenBtn).toBeTruthy()
    await reopenBtn!.click()
    await flushPromises()
    expect(reopenEvent).toHaveBeenCalledWith(7)
  })
})
