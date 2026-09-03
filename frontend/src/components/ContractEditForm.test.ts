import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ContractEditForm from '@/components/ContractEditForm.vue'
import type { ContractRow } from '@/types'

const sampleRow: ContractRow = {
  id: 11,
  employment_id: 4,
  full_name: 'Иван Иванов',
  start_date: '2024-01-01',
  end_date: '2025-01-01',
  term_years: 1,
  days_left: 100,
  is_active: true,
  renewal_report_event: {
    id: 55,
    event_date: '2024-09-01',
    completed_date: null,
    status: 'planned',
    effective_status: 'planned',
  },
}

const { updateContract } = vi.hoisted(() => ({
  updateContract: vi.fn(async () => ({})),
}))

vi.mock('@/api/client', () => ({
  api: { updateContract },
}))

describe('ContractEditForm', () => {
  it('sends term, end date and report date without start_date', async () => {
    const wrapper = mount(ContractEditForm, { props: { row: sampleRow } })

    expect(wrapper.text()).toContain('1 января 2024 г.')
    expect((wrapper.get('input[name="report_date"]').element as HTMLInputElement).value).toBe(
      '2024-09-01',
    )

    await wrapper.get('select').setValue('3')
    await wrapper.get('input[name="end_date"]').setValue('2027-01-01')
    expect(wrapper.text()).toContain('1 января 2024 г.')
    expect((wrapper.get('input[name="report_date"]').element as HTMLInputElement).value).toBe(
      '2026-09-01',
    )

    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(updateContract).toHaveBeenCalledWith(11, {
      term_years: 3,
      end_date: '2027-01-01',
      report_date: '2026-09-01',
    })
    expect(wrapper.emitted('saved')).toBeTruthy()
  })

  it('keeps a custom report date when the end date later changes', async () => {
    updateContract.mockClear()
    const wrapper = mount(ContractEditForm, { props: { row: sampleRow } })

    await wrapper.get('input[name="report_date"]').setValue('2024-10-15')
    await wrapper.get('input[name="end_date"]').setValue('2026-01-01')
    expect((wrapper.get('input[name="report_date"]').element as HTMLInputElement).value).toBe(
      '2024-10-15',
    )

    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(updateContract).toHaveBeenCalledWith(11, {
      term_years: 1,
      end_date: '2026-01-01',
      report_date: '2024-10-15',
    })
  })

  it('requires both contract fields', async () => {
    updateContract.mockClear()
    const wrapper = mount(ContractEditForm, { props: { row: sampleRow } })

    await wrapper.get('input[name="end_date"]').setValue('')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(updateContract).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Укажите срок договора и дату окончания')
  })
})
