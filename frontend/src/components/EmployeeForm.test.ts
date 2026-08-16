import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EmployeeForm from '@/components/EmployeeForm.vue'
import { useAuthStore } from '@/stores/auth'
import type { Grade } from '@/types'

const grades: Grade[] = [
  { id: 1, name: 'Junior', rank: 1, min_years: 1, is_active: true },
  { id: 2, name: 'Middle', rank: 2, min_years: 1.5, is_active: true },
]

const { createEmployee, updateEmployee, gradeCatalog } = vi.hoisted(() => ({
  createEmployee: vi.fn(async () => ({})),
  updateEmployee: vi.fn(async () => ({})),
  gradeCatalog: vi.fn(async () => grades),
}))

vi.mock('@/api/client', () => ({
  api: {
    gradeCatalog,
    createEmployee,
    updateEmployee,
  },
}))

describe('EmployeeForm', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'hr', full_name: 'HR User', role: 'hr' }
    createEmployee.mockClear()
    updateEmployee.mockClear()
    gradeCatalog.mockClear()
  })

  it('calculates contract_end when hire_date and term_years are changed', async () => {
    const wrapper = mount(EmployeeForm)
    await flushPromises()

    const fullNameInput = wrapper.findAll('input')[0]
    const dateInputs = wrapper.findAll('input[type="date"]')
    const hireDateInput = dateInputs[0]
    const contractEndInput = dateInputs[2]

    const selects = wrapper.findAll('select')
    const educationSelect = selects[0]
    const termSelect = selects[3]

    await fullNameInput.setValue('Иванов Иван')
    await educationSelect.setValue('no')
    await hireDateInput.setValue('2024-09-01')
    await hireDateInput.trigger('change')
    await termSelect.setValue('2')
    await termSelect.trigger('change')
    await flushPromises()

    expect((contractEndInput.element as HTMLInputElement).value).toBe('2026-09-01')

    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(createEmployee).toHaveBeenCalledWith(
      expect.objectContaining({
        full_name: 'Иванов Иван',
        hire_date: '2024-09-01',
        contract_term_years: 2,
        contract_end: '2026-09-01',
      }),
    )
    expect(wrapper.emitted('saved')).toBeTruthy()
  })

  it('calculates term_years when contract_end is changed manually', async () => {
    const wrapper = mount(EmployeeForm)
    await flushPromises()

    const fullNameInput = wrapper.findAll('input')[0]
    const dateInputs = wrapper.findAll('input[type="date"]')
    const hireDateInput = dateInputs[0]
    const contractEndInput = dateInputs[2]

    const selects = wrapper.findAll('select')
    const educationSelect = selects[0]
    const termSelect = selects[3]

    await fullNameInput.setValue('Петров Петр')
    await educationSelect.setValue('yes')
    await hireDateInput.setValue('2024-09-01')
    await hireDateInput.trigger('change')
    await contractEndInput.setValue('2027-09-01')
    await contractEndInput.trigger('change')
    await flushPromises()

    expect((termSelect.element as HTMLSelectElement).value).toBe('3')

    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(createEmployee).toHaveBeenCalledWith(
      expect.objectContaining({
        full_name: 'Петров Петр',
        hire_date: '2024-09-01',
        contract_term_years: 3,
        contract_end: '2027-09-01',
      }),
    )
  })

  it('shows error when contract_end is before or equal to hire_date', async () => {
    const wrapper = mount(EmployeeForm)
    await flushPromises()

    const fullNameInput = wrapper.findAll('input')[0]
    const dateInputs = wrapper.findAll('input[type="date"]')
    const hireDateInput = dateInputs[0]
    const contractEndInput = dateInputs[2]
    const educationSelect = wrapper.findAll('select')[0]

    await fullNameInput.setValue('Ошибкин Ошибка')
    await educationSelect.setValue('no')
    await hireDateInput.setValue('2024-09-01')
    await contractEndInput.setValue('2024-08-01')

    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(createEmployee).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Дата окончания договора должна быть позже даты начала работы')
  })

  it('requires an explicit university choice', async () => {
    const wrapper = mount(EmployeeForm)
    await flushPromises()

    await wrapper.findAll('input')[0].setValue('Без Выбора')
    await wrapper.findAll('input[type="date"]')[0].setValue('2024-01-01')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(createEmployee).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Укажите наличие высшего образования')
  })
})
