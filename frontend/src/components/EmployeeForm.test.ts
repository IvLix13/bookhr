import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EmployeeForm from '@/components/EmployeeForm.vue'
import { useAuthStore } from '@/stores/auth'
import type { Employee, Grade } from '@/types'

const grades: Grade[] = [
  { id: 1, name: 'Junior', rank: 1, min_years: 1, is_active: true },
  { id: 2, name: 'Middle', rank: 2, min_years: 1.5, is_active: true },
]

const { createEmployee, updateEmployee, gradeCatalog, employeePeriods } = vi.hoisted(() => ({
  createEmployee: vi.fn(async () => ({})),
  updateEmployee: vi.fn(async () => ({})),
  employeePeriods: vi.fn(async (id: number) => [{ id, hire_date: '2020-01-01', dismissal_date: null, status: 'active' }]),
  gradeCatalog: vi.fn(async () => grades),
}))

vi.mock('@/api/client', () => ({
  api: {
    gradeCatalog,
    createEmployee,
    updateEmployee,
    employeePeriods,
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
    employeePeriods.mockClear()
  })

  it('submits contract term and end date as entered without recalculation', async () => {
    const wrapper = mount(EmployeeForm)
    await flushPromises()

    const fullNameInput = wrapper.findAll('input')[0]
    const hireDateInput = wrapper.get('input[name="period_hire_date"]')
    const contractEndInput = wrapper.get('input[name="contract_end"]')

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

  it('keeps leading zeroes and submits directory fields separately from grades', async () => {
    const wrapper = mount(EmployeeForm, {
      props: { initial: {
        id: 7, full_name: 'Иванов Иван', title: 'Инженер', hire_date: '2020-01-01',
        education_status: 'yes', cardnumber: '00123', fio_short: 'Иванов И.',
        position_short_name: 'И', formal_department_short_name: '2 отдел',
        formal_department_name: 'Второй отдел',
      } as Employee },
    })
    await flushPromises()
    expect((wrapper.get('input[name="cardnumber"]').element as HTMLInputElement).value).toBe('00123')
    await wrapper.get('input[name="formal_department_name"]').setValue('Новый отдел')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()
    expect(updateEmployee).toHaveBeenCalledWith(7, expect.objectContaining({
      cardnumber: '00123', fio_short: 'Иванов И.', position_short_name: 'И',
      formal_department_short_name: '2 отдел', formal_department_name: 'Новый отдел',
      position_grade_id: null, actual_grade_id: null,
    }))
  })

  it('disables directory inputs for readonly viewers', async () => {
    const wrapper = mount(EmployeeForm, { props: { readonly: true } })
    await flushPromises()
    expect(wrapper.get('input[name="cardnumber"]').attributes()).toHaveProperty('disabled')
    expect(wrapper.get('input[name="formal_department_name"]').attributes()).toHaveProperty('disabled')
    await wrapper.get('form').trigger('submit.prevent')
    expect(createEmployee).not.toHaveBeenCalled()
  })

  it('creates three work periods and submits the latest hire date', async () => {
    const wrapper = mount(EmployeeForm)
    await flushPromises()
    await wrapper.findAll('input')[0].setValue('Иванов Иван')
    await wrapper.findAll('select')[0].setValue('yes')

    await wrapper.get('input[name="period_hire_date"]').setValue('2000-01-01')
    await wrapper.get('input[name="period_dismissal_date"]').setValue('2005-01-01')
    await wrapper.get('button.period-add').trigger('click')
    await wrapper.findAll('input[name="period_hire_date"]')[1].setValue('2010-01-01')
    await wrapper.findAll('input[name="period_dismissal_date"]')[1].setValue('2015-01-01')
    await wrapper.get('button.period-add').trigger('click')
    await wrapper.findAll('input[name="period_hire_date"]')[2].setValue('2020-01-01')

    expect(wrapper.find('button.period-add').exists()).toBe(false)
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(createEmployee).toHaveBeenCalledWith(expect.objectContaining({
      hire_date: '2020-01-01',
      periods: [
        { id: null, hire_date: '2000-01-01', dismissal_date: '2005-01-01' },
        { id: null, hire_date: '2010-01-01', dismissal_date: '2015-01-01' },
        { id: null, hire_date: '2020-01-01', dismissal_date: null },
      ],
    }))
  })

  it('loads saved periods for editing and preserves their IDs', async () => {
    employeePeriods.mockResolvedValueOnce([
      { id: 1, hire_date: '2010-01-01', dismissal_date: '2015-01-01', status: 'dismissed' },
      { id: 7, hire_date: '2020-01-01', dismissal_date: null, status: 'active' },
    ])
    const wrapper = mount(EmployeeForm, {
      props: { initial: {
        id: 7, full_name: 'Иванов Иван', title: 'Инженер', hire_date: '2020-01-01',
        education_status: 'yes',
      } as Employee },
    })
    await flushPromises()
    expect(employeePeriods).toHaveBeenCalledWith(7)
    expect(wrapper.findAll('input[name="period_hire_date"]')).toHaveLength(2)
    expect(wrapper.find('button.period-remove').exists()).toBe(false)

    await wrapper.findAll('input[name="period_hire_date"]')[1].setValue('2020-02-01')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()
    expect(updateEmployee).toHaveBeenCalledWith(7, expect.objectContaining({
      hire_date: '2020-02-01',
      periods: [
        { id: 1, hire_date: '2010-01-01', dismissal_date: '2015-01-01' },
        { id: 7, hire_date: '2020-02-01', dismissal_date: null },
      ],
    }))
  })

  it('does not submit overlapping work periods', async () => {
    const wrapper = mount(EmployeeForm)
    await flushPromises()
    await wrapper.findAll('input')[0].setValue('Проверка Периодов')
    await wrapper.findAll('select')[0].setValue('yes')
    await wrapper.get('input[name="period_hire_date"]').setValue('2010-01-01')
    await wrapper.get('input[name="period_dismissal_date"]').setValue('2015-01-01')
    await wrapper.get('button.period-add').trigger('click')
    await wrapper.findAll('input[name="period_hire_date"]')[1].setValue('2014-01-01')

    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()
    expect(createEmployee).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('должно быть позже увольнения предыдущего')
  })

})
