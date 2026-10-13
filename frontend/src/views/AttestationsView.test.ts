import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AttestationsView from '@/views/AttestationsView.vue'
import { useAuthStore } from '@/stores/auth'
import type { AttestationRow } from '@/api/client'

const row: AttestationRow = {
  employment_id: 4,
  full_name: 'Иван Иванов',
  attestation_date: '2026-10-30',
  attestation_preparation_date: '2026-10-16',
  attestation_event_id: 55,
  attestation_status: 'planned',
}

const { attestations, attestation, updateAttestation } = vi.hoisted(() => ({
  attestations: vi.fn(), attestation: vi.fn(), updateAttestation: vi.fn(),
}))
vi.mock('@/api/client', () => ({ api: { attestations, attestation, updateAttestation } }))

const modalStub = {
  props: ['open', 'eventId'], emits: ['close', 'changed'],
  template: `<div v-if="open" class="event-modal-stub">
    <span class="modal-event-id">{{ eventId }}</span>
    <button class="complete" @click="$emit('changed')">Выполнить</button>
    <button class="close-event" @click="$emit('close')">Закрыть событие</button>
  </div>`,
}

describe('AttestationsView', () => {
  const wrappers: ReturnType<typeof mount>[] = []
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    attestations.mockReset().mockResolvedValue({ items: [row], total: 1, page: 1, per_page: 25 })
    attestation.mockReset().mockResolvedValue(row)
    updateAttestation.mockReset().mockResolvedValue(row)
  })
  afterEach(() => { wrappers.splice(0).forEach((wrapper) => wrapper.unmount()) })

  async function mountView(role: 'hr' | 'viewer' = 'hr') {
    useAuthStore().user = { id: 1, username: role, full_name: role, role }
    const wrapper = mount(AttestationsView, {
      global: { stubs: { teleport: true, EventDetailModal: modalStub } },
    })
    wrappers.push(wrapper)
    await flushPromises()
    return wrapper
  }

  it('shows the preparation column with the server date and requests server sorting', async () => {
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('Дата подготовки документов')
    expect(wrapper.text()).toContain('16 октября 2026')
    const heading = wrapper.findAll('th').find((item) => item.text().includes('Дата подготовки документов'))!
    await heading.find('button').trigger('click')
    await flushPromises()
    expect(attestations).toHaveBeenLastCalledWith(expect.objectContaining({ sort: 'attestation_preparation_date' }))
  })

  it('shows empty dates and does not offer an event without a scheduled attestation', async () => {
    attestations.mockResolvedValue({ items: [{ ...row, attestation_date: null,
      attestation_preparation_date: null, attestation_event_id: null, attestation_status: null }], total: 1, page: 1, per_page: 25 })
    const wrapper = await mountView()
    await wrapper.get('.data-table-row').trigger('click')
    expect(wrapper.text()).toContain('Дата подготовки документов: —')
    expect(wrapper.findAll('button').some((item) => item.text() === 'Мероприятие')).toBe(false)
  })

  it('saves the date and displays the recalculated server value', async () => {
    const updated = { ...row, attestation_date: '2026-11-06', attestation_preparation_date: '2026-10-23' }
    updateAttestation.mockResolvedValue(updated)
    attestations.mockResolvedValueOnce({ items: [row], total: 1, page: 1, per_page: 25 })
      .mockResolvedValue({ items: [updated], total: 1, page: 1, per_page: 25 })
    const wrapper = await mountView()
    await wrapper.get('.data-table-row').trigger('click')
    await wrapper.get('input[type="date"]').setValue('2026-11-06')
    const eventButton = wrapper.findAll('button').find((item) => item.text() === 'Мероприятие')!
    expect(eventButton.attributes('disabled')).toBeDefined()
    await wrapper.findAll('button').find((item) => item.text() === 'Сохранить')!.trigger('click')
    await flushPromises()
    expect(updateAttestation).toHaveBeenCalledWith(4, '2026-11-06')
    expect(wrapper.text()).toContain('Дата подготовки документов: 23 октября 2026')
    expect(wrapper.get('input[type="date"]').element).toHaveProperty('value', '2026-11-06')
  })

  it('refreshes both the open window and the table after completion even if the row leaves this page', async () => {
    const wrapper = await mountView()
    await wrapper.get('.data-table-row').trigger('click')
    await wrapper.findAll('button').find((item) => item.text() === 'Мероприятие')!.trigger('click')
    expect(wrapper.get('.modal-event-id').text()).toBe('55')
    attestation.mockResolvedValue({ ...row, attestation_status: 'completed' })
    attestations.mockResolvedValue({ items: [], total: 0, page: 1, per_page: 25 })
    await wrapper.get('.complete').trigger('click')
    await flushPromises()
    await wrapper.get('.close-event').trigger('click')
    expect(attestation).toHaveBeenCalledWith(4)
    expect(wrapper.text()).toContain('Выполнено')
    expect(attestations.mock.calls.length).toBeGreaterThan(1)
  })

  it('keeps the draft on a save error and blocks repeat submission while saving', async () => {
    const wrapper = await mountView()
    await wrapper.get('.data-table-row').trigger('click')
    await wrapper.get('input[type="date"]').setValue('2026-11-06')
    let rejectSave: (reason: Error) => void = () => {}
    updateAttestation.mockImplementation(() => new Promise((_resolve, reject) => { rejectSave = reject }))
    const saveButton = wrapper.findAll('button').find((item) => item.text() === 'Сохранить')!
    await saveButton.trigger('click')
    await flushPromises()
    expect(updateAttestation).toHaveBeenCalledTimes(1)
    expect(wrapper.findAll('button').find((item) => item.text() === 'Сохранение…')!.attributes('disabled')).toBeDefined()
    rejectSave(new Error('Ошибка сохранения'))
    await flushPromises()
    expect(wrapper.text()).toContain('Ошибка сохранения')
    expect(wrapper.get('input[type="date"]').element).toHaveProperty('value', '2026-11-06')
  })

  it('does not expose editing or event actions to viewer', async () => {
    const wrapper = await mountView('viewer')
    await wrapper.get('.data-table-row').trigger('click')
    expect(wrapper.find('input[type="date"]').exists()).toBe(false)
    expect(wrapper.find('.event-modal-stub').exists()).toBe(false)
    expect(updateAttestation).not.toHaveBeenCalled()
  })
})
