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

  it('submits contract term and end date as entered without recalculation', async () => {
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
    await hireDateInput.setValue('2020-01-01')
    await termSelect.setValue('3')
    await contractEndInput.setValue('2027-06-01')

    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(createEmployee).toHaveBeenCalledWith(
      expect.objectContaining({
        full_name: 'Иванов Иван',
        hire_date: '2020-01-01',
        contract_term_years: 3,
        contract_end: '2027-06-01',
      }),
    )
    expect(wrapper.emitted('saved')).toBeTruthy()
  })

  it('requires both contract fields when one is filled', async () => {
    const wrapper = mount(EmployeeForm)
    await flushPromises()

    await wrapper.findAll('input')[0].setValue('Петров Петр')
    await wrapper.findAll('select')[0].setValue('yes')
    await wrapper.findAll('input[type="date"]')[0].setValue('2024-09-01')
    await wrapper.findAll('select')[3].setValue('2')

    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(createEmployee).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Укажите срок договора и дату окончания')
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
