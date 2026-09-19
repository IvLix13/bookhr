import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import OnboardingView from '@/views/OnboardingView.vue'
import OnboardingCellEditor from '@/components/OnboardingCellEditor.vue'
import OnboardingColumns from '@/components/OnboardingColumns.vue'
import { ApiError } from '@/api/errors'
import type { OnboardingColumn } from '@/types/onboarding'

const mock = vi.hoisted(() => ({
  editable: true,
  columns: vi.fn(), plans: vi.fn(), employees: vi.fn(), createPlan: vi.fn(),
  saveCell: vi.fn(), createColumn: vi.fn(), updateColumn: vi.fn(), orderColumns: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ canEdit: () => mock.editable }) }))
vi.mock('@/api/client', () => ({ api: {
  onboardingColumns: mock.columns, onboardingPlans: mock.plans, employees: mock.employees,
  createOnboardingPlan: mock.createPlan, updateOnboardingCell: mock.saveCell,
  createOnboardingColumn: mock.createColumn, updateOnboardingColumn: mock.updateColumn,
  orderOnboardingColumns: mock.orderColumns,
} }))
const column: OnboardingColumn = { id: 1, title: 'NDA', field_type: 'stage', sort_order: 0, is_archived: false, version: 1 }
const cell = { version: 2, text_value: null, date_value: null, planned_date: '2026-10-01', is_completed: false, completed_date: null }

beforeEach(() => {
  vi.clearAllMocks()
  mock.editable = true
  mock.columns.mockResolvedValue([{ ...column }])
  mock.plans.mockResolvedValue({ items: [{ id: 1, employment_id: 2, full_name: 'Иванов', grade: 'Junior', employment_status: 'active', cells: { '1': { ...cell } } }], page: 1, per_page: 25, total: 1, pages: 1 })
  mock.employees.mockResolvedValue({ items: [{ id: 2, full_name: 'Петров', hire_date: '2020-01-01', status: 'active' }], page: 1, pages: 1, total: 1 })
  mock.createPlan.mockResolvedValue({ id: 2 })
  mock.saveCell.mockResolvedValue({ ...cell, version: 3 })
  mock.createColumn.mockResolvedValue({ ...column, id: 2 })
  mock.updateColumn.mockResolvedValue({ ...column, version: 2 })
  mock.orderColumns.mockResolvedValue([])
})

describe('Onboarding table', () => {
  it('renders system columns and opens a cell editor', async () => {
    const wrapper = mount(OnboardingView, { global: { stubs: { teleport: true } } })
    await flushPromises()
    expect(wrapper.text()).toContain('Иванов')
    expect(wrapper.text()).toContain('Junior')
    expect(wrapper.findAll('th').map(x => x.text())).toEqual(['№', 'Грейд', 'ФИО', 'NDA'])
    await wrapper.get('.cell-button').trigger('click')
    expect(wrapper.findComponent(OnboardingCellEditor).exists()).toBe(true)
    wrapper.unmount()
  })
  it('viewer sees data but cannot edit or configure', async () => {
    mock.editable = false
    const wrapper = mount(OnboardingView)
    await flushPromises()
    expect(wrapper.text()).toContain('Иванов')
    expect(wrapper.text()).not.toContain('Настроить столбцы')
    expect(wrapper.text()).not.toContain('Добавить сотрудника')
    expect(wrapper.find('.cell-button').exists()).toBe(false)
    wrapper.unmount()
  })
  it('searches on submit and creates a plan for a selected employee', async () => {
    const wrapper = mount(OnboardingView)
    await flushPromises()
    await wrapper.get('input[aria-label="Поиск планов по ФИО"]').setValue('Иванов')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mock.plans).toHaveBeenLastCalledWith({ q: 'Иванов', page: 1, per_page: 25 })
    await wrapper.findAll('button').find(b => b.text() === 'Добавить сотрудника')!.trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find(b => b.text() === 'Создать план')!.trigger('click')
    await flushPromises()
    expect(mock.createPlan).toHaveBeenCalledWith(2)
    wrapper.unmount()
  })
})

describe('Cell editor', () => {
  function editor() {
    return mount(OnboardingCellEditor, { props: { planId: 1, employeeName: 'Иванов', column: { ...column }, cell: { ...cell } }, global: { stubs: { teleport: true } } })
  }
  it('sets completion date and sends optimistic versions', async () => {
    const wrapper = editor()
    await wrapper.get('input[type="checkbox"]').setValue(true)
    const dates = wrapper.findAll('input[type="date"]')
    expect((dates[1]!.element as HTMLInputElement).value).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    await dates[1]!.setValue('2026-09-19')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mock.saveCell).toHaveBeenCalledWith(1, 1, { version: 2, column_version: 1, planned_date: '2026-10-01', is_completed: true, completed_date: '2026-09-19' })
    expect(wrapper.emitted('saved')).toHaveLength(1)
    wrapper.unmount()
  })
  it('preserves input on conflict without allowing stale retry', async () => {
    mock.saveCell.mockRejectedValueOnce(new ApiError('Конфликт', 409))
    const wrapper = editor()
    await wrapper.get('input[type="date"]').setValue('2026-11-01')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.emitted('conflict')).toHaveLength(1)
    expect((wrapper.get('input[type="date"]').element as HTMLInputElement).value).toBe('2026-11-01')
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
  it('cancel does not save', async () => {
    const wrapper = editor()
    await wrapper.findAll('button').find(b => b.text() === 'Отмена')!.trigger('click')
    expect(mock.saveCell).not.toHaveBeenCalled()
    expect(wrapper.emitted('close')).toHaveLength(1)
    wrapper.unmount()
  })
})

describe('Column management', () => {
  it('creates typed columns and confirms archival', async () => {
    const wrapper = mount(OnboardingColumns, { props: { columns: [{ ...column }] } })
    await wrapper.get('input').setValue('Отдел')
    await wrapper.get('select').setValue('text')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mock.createColumn).toHaveBeenCalledWith({ title: 'Отдел', field_type: 'text' })
    await wrapper.findAll('button').find(b => b.text() === 'В архив')!.trigger('click')
    expect(mock.updateColumn).not.toHaveBeenCalled()
    await wrapper.findAll('button').find(b => b.text() === 'Архивировать')!.trigger('click')
    await flushPromises()
    expect(mock.updateColumn).toHaveBeenCalledWith(1, { version: 1, is_archived: true })
    wrapper.unmount()
  })
  it('reorders using all column versions', async () => {
    const wrapper = mount(OnboardingColumns, { props: { columns: [{ ...column }, { ...column, id: 2, title: 'Отдел', sort_order: 1 }] } })
    await wrapper.get('button[aria-label="Переместить NDA вправо"]').trigger('click')
    await flushPromises()
    expect(mock.orderColumns).toHaveBeenCalledWith([{ id: 2, version: 1 }, { id: 1, version: 1 }])
    wrapper.unmount()
  })
})
