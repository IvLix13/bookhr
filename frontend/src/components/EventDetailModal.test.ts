import { DOMWrapper, flushPromises, mount } from '@vue/test-utils'
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

const { getEvent, completeEvent, cancelEvent, reopenEvent, updateEvent, deleteEvent } = vi.hoisted(() => ({
  getEvent: vi.fn(async () => plannedEvent),
  completeEvent: vi.fn(async () => ({ ...plannedEvent, status: 'completed' })),
  cancelEvent: vi.fn(async () => ({ ...plannedEvent, status: 'cancelled' })),
  reopenEvent: vi.fn(async () => plannedEvent),
  updateEvent: vi.fn(async () => plannedEvent),
  deleteEvent: vi.fn(async () => ({})),
}))

vi.mock('@/api/client', () => ({
  api: {
    getEvent,
    completeEvent,
    cancelEvent,
    reopenEvent,
    updateEvent,
    deleteEvent,
    employees: vi.fn(async () => ({ items: [] })),
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
    updateEvent.mockReset()
    getEvent.mockResolvedValue(plannedEvent)
    completeEvent.mockResolvedValue({ ...plannedEvent, status: 'completed' })
    cancelEvent.mockResolvedValue({ ...plannedEvent, status: 'cancelled' })
    reopenEvent.mockResolvedValue(plannedEvent)
    updateEvent.mockResolvedValue(plannedEvent)
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
    expect(document.body.textContent).toContain('1 июля 2026 г.')
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

  it('requires a comment before cancelling', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await mountModal('hr')
    const cancelBtn = Array.from(document.body.querySelectorAll('button')).find((button) =>
      button.textContent?.includes('Отменить'),
    ) as HTMLButtonElement
    expect(cancelBtn.disabled).toBe(true)

    const input = document.body.querySelector(
      'input[aria-label="Комментарий к действию"]',
    ) as HTMLInputElement
    await new DOMWrapper(input).setValue('Дубль')
    expect(cancelBtn.disabled).toBe(false)

    await cancelBtn.click()
    await flushPromises()
    expect(cancelEvent).toHaveBeenCalledWith(7, 'Дубль')
  })

  it('shows the last status change login and time', async () => {
    getEvent.mockResolvedValueOnce({
      ...plannedEvent,
      last_status_change: {
        username: 'hr_user',
        changed_at: '2026-07-20T12:00:00',
        new_status: 'planned',
        comment: 'Auto-created by rule engine',
      },
    })
    await mountModal('hr')
    const text = document.body.textContent ?? ''
    expect(text).toContain('hr_user')
    expect(text).toContain('20 июля 2026 г.')
    expect(text).toContain('Последнее изменение')
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

  it('completes contract renewal event with extension term', async () => {
    const contractEvent: EventItem = {
      ...plannedEvent,
      title: 'Подготовить рапорт на продление Договора: Иванов',
      reference_type: 'contract',
      reference_id: 10,
    }
    getEvent.mockResolvedValueOnce(contractEvent)
    const wrapper = await mountModal('hr')
    expect(document.body.textContent).toContain('Срок продления договора:')

    const select = document.body.querySelector('#extension-term-select') as HTMLSelectElement
    expect(select).toBeTruthy()
    select.value = '3'
    await select.dispatchEvent(new Event('change'))

    const buttons = Array.from(document.body.querySelectorAll('button'))
    const completeBtn = buttons.find((button) => button.textContent?.includes('Выполнить'))
    await completeBtn!.click()
    await flushPromises()

    expect(completeEvent).toHaveBeenCalledWith(7, undefined, { extension_term_years: 3 })
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('saves a custom report date for an open contract renewal event', async () => {
    const contractEvent: EventItem = {
      ...plannedEvent,
      title: 'Подготовить рапорт на продление Договора: Иванов',
      reference_type: 'contract',
      reference_id: 10,
    }
    getEvent.mockResolvedValue(contractEvent)
    updateEvent.mockResolvedValue({ ...contractEvent, event_date: '2026-06-01' })
    const wrapper = await mountModal('hr')

    const dateEl = document.body.querySelector('#report-date-input')
    expect(dateEl).not.toBeNull()
    const dateInput = new DOMWrapper(dateEl as HTMLInputElement)
    expect((dateInput.element as HTMLInputElement).value).toBe('2026-07-24')
    await dateInput.setValue('2026-06-01')

    const saveBtn = Array.from(document.body.querySelectorAll('button')).find((button) =>
      button.textContent?.includes('Сохранить дату'),
    )
    expect(saveBtn).toBeTruthy()
    await saveBtn!.click()
    await flushPromises()

    expect(updateEvent).toHaveBeenCalledWith(7, { event_date: '2026-06-01' })
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('saves a custom report date even when the renewal event is completed', async () => {
    const completedContractEvent: EventItem = {
      ...completedEvent,
      title: 'Подготовить рапорт на продление Договора: Иванов',
      reference_type: 'contract',
      reference_id: 10,
      completed_at: '2026-07-20T12:00:00',
    }
    getEvent.mockResolvedValue(completedContractEvent)
    updateEvent.mockResolvedValue({
      ...completedContractEvent,
      event_date: '2026-06-01',
      completed_at: '2026-06-01T12:00:00',
    })
    const wrapper = await mountModal('hr')

    expect(document.body.textContent).toContain('Переоткрыть')
    const dateEl = document.body.querySelector('#report-date-input')
    expect(dateEl).not.toBeNull()
    const dateInput = new DOMWrapper(dateEl as HTMLInputElement)
    expect((dateInput.element as HTMLInputElement).value).toBe('2026-07-20')
    await dateInput.setValue('2026-06-01')

    const saveBtn = Array.from(document.body.querySelectorAll('button')).find((button) =>
      button.textContent?.includes('Сохранить дату'),
    )
    expect(saveBtn).toBeTruthy()
    await saveBtn!.click()
    await flushPromises()

    expect(updateEvent).toHaveBeenCalledWith(7, { event_date: '2026-06-01' })
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('requires a grade choice when several candidates share the next rank', async () => {
    const gradeEvent: EventItem = {
      ...plannedEvent,
      event_type: 'grade',
      grade_completion: {
        next_rank: 2,
        candidates: [
          { id: 2, name: 'Middle A', rank: 2, min_years: 1 },
          { id: 3, name: 'Middle B', rank: 2, min_years: 1 },
        ],
        requires_selection: true,
        eligible_date: '2025-01-01',
        blocked_reason: null,
      },
    }
    getEvent.mockResolvedValueOnce(gradeEvent)
    await mountModal('hr')

    const select = document.body.querySelector('#target-grade-select') as HTMLSelectElement
    const completeBtn = Array.from(document.body.querySelectorAll('button')).find((button) =>
      button.textContent?.includes('Выполнить'),
    )!
    expect(select).toBeTruthy()
    expect(completeBtn.disabled).toBe(true)

    select.value = '3'
    select.dispatchEvent(new Event('change'))
    await flushPromises()
    expect(completeBtn.disabled).toBe(false)

    await completeBtn.click()
    await flushPromises()
    expect(completeEvent).toHaveBeenCalledWith(7, undefined, { target_grade_id: 3 })
  })

  it('completes passport preparation with new valid until date', async () => {
    const passportEvent: EventItem = {
      ...plannedEvent,
      event_type: 'passport',
      title: 'Подготовка документов для паспорта: Иванов',
      reference_type: 'passport',
      reference_id: 5,
      passport_completion: {
        current_valid_until: '2026-09-01',
        suggested_new_valid_until: '2031-09-01',
        requires_new_date: true,
      },
    }
    getEvent.mockResolvedValueOnce(passportEvent)
    const wrapper = await mountModal('hr')

    const dateInput = document.body.querySelector('#new-passport-date') as HTMLInputElement
    expect(dateInput).toBeTruthy()
    expect(dateInput.value).toBe('2031-09-01')

    const completeBtn = Array.from(document.body.querySelectorAll('button')).find((button) =>
      button.textContent?.includes('Выполнить'),
    )!
    await completeBtn.click()
    await flushPromises()

    expect(completeEvent).toHaveBeenCalledWith(7, undefined, {
      new_passport_valid_until: '2031-09-01',
    })
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('shows edit and delete for manual open events', async () => {
    getEvent.mockResolvedValueOnce({ ...plannedEvent, source: 'manual' })
    await mountModal('hr')
    const text = document.body.textContent ?? ''
    expect(text).toContain('Редактировать')
    expect(text).toContain('Удалить')
  })

  it('hides edit and delete for rule events', async () => {
    getEvent.mockResolvedValueOnce({ ...plannedEvent, source: 'rule' })
    await mountModal('hr')
    const text = document.body.textContent ?? ''
    expect(text).not.toContain('Редактировать')
    expect(text).not.toContain('Удалить')
  })

  it('deletes manual event and closes modal', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    getEvent.mockResolvedValueOnce({ ...plannedEvent, source: 'manual' })
    const wrapper = await mountModal('hr')
    const deleteBtn = Array.from(document.body.querySelectorAll('button')).find((button) =>
      button.textContent?.includes('Удалить'),
    )
    expect(deleteBtn).toBeTruthy()
    await deleteBtn!.click()
    await flushPromises()
    expect(deleteEvent).toHaveBeenCalledWith(7)
    expect(wrapper.emitted('changed')).toBeTruthy()
    expect(wrapper.emitted('close')).toBeTruthy()
  })
})
