import { DOMWrapper, flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import OnboardingView from '@/views/OnboardingView.vue'
import OnboardingCellEditor from '@/components/OnboardingCellEditor.vue'
import OnboardingColumns from '@/components/OnboardingColumns.vue'
import OnboardingColumnsModal from '@/components/OnboardingColumnsModal.vue'
import { ApiError } from '@/api/errors'
import type { OnboardingColumn } from '@/types/onboarding'

const mock = vi.hoisted(() => ({
  editable: true,
  columns: vi.fn(), plans: vi.fn(), employees: vi.fn(), createPlan: vi.fn(),
  saveCell: vi.fn(), createColumn: vi.fn(), updateColumn: vi.fn(), orderColumns: vi.fn(),
  downloadOnboarding: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ canEdit: () => mock.editable }) }))
vi.mock('@/api/client', () => ({ api: {
  onboardingColumns: mock.columns, onboardingPlans: mock.plans, employees: mock.employees,
  createOnboardingPlan: mock.createPlan, updateOnboardingCell: mock.saveCell,
  createOnboardingColumn: mock.createColumn, updateOnboardingColumn: mock.updateColumn,
  orderOnboardingColumns: mock.orderColumns,
  downloadOnboarding: mock.downloadOnboarding,
} }))
const column: OnboardingColumn = { id: 1, title: 'NDA', field_type: 'stage', sort_order: 0, is_archived: false, version: 1 }
const cell = { version: 2, text_value: null, date_value: null, planned_date: '2026-10-01', is_completed: false, is_not_required: false, completed_date: null }

beforeEach(() => {
  vi.resetAllMocks()
  mock.editable = true
  mock.columns.mockResolvedValue([{ ...column }])
  mock.plans.mockResolvedValue({ items: [{ id: 1, employment_id: 2, full_name: 'Иванов', grade: 'Junior', employment_status: 'active', cells: { '1': { ...cell } } }], page: 1, per_page: 25, total: 1, pages: 1 })
  mock.employees.mockResolvedValue({ items: [{ id: 2, full_name: 'Петров', hire_date: '2020-01-01', status: 'active' }], page: 1, pages: 1, total: 1 })
  mock.createPlan.mockResolvedValue({ id: 2 })
  mock.saveCell.mockResolvedValue({ ...cell, version: 3 })
  mock.createColumn.mockResolvedValue({ ...column, id: 2 })
  mock.updateColumn.mockResolvedValue({ ...column, version: 2 })
  mock.orderColumns.mockResolvedValue([])
  mock.downloadOnboarding.mockResolvedValue(undefined)
})

describe('Onboarding table', () => {
  it('renders employees as columns and edits the selected employee and stage', async () => {
    mock.columns.mockResolvedValueOnce([column, { ...column, id: 2, title: 'Пропуск', field_type: 'checkbox' }, { ...column, id: 3, title: 'Архив', is_archived: true }])
    mock.plans.mockResolvedValueOnce({ items: [
      { id: 10, full_name: 'Иванов', grade: 'Junior', cells: { '1': cell } },
      { id: 20, full_name: 'Петров', grade: 'Senior', cells: { '2': { ...cell, is_completed: true } } },
    ], total: 2, pages: 1 })
    const wrapper = mount(OnboardingView, { global: { stubs: { teleport: true } } })
    await flushPromises()
    expect(wrapper.findAll('thead th').map(x => x.text())).toEqual(['Этап / сотрудник', 'Иванов', 'Петров'])
    expect(wrapper.findAll('tbody th').map(x => x.text())).toEqual(['№', 'Грейд', 'NDA', 'Пропуск'])
    expect(wrapper.findAll('tbody tr')[1]!.findAll('td').map(x => x.text())).toEqual(['Junior', 'Senior'])
    await wrapper.get('button[aria-label="Пропуск, Петров: ✓"]').trigger('click')
    expect(wrapper.getComponent(OnboardingCellEditor).props('planId')).toBe(20)
    expect(wrapper.getComponent(OnboardingCellEditor).props('column').id).toBe(2)
    wrapper.unmount()
  })
  it('renders system columns and opens a cell editor', async () => {
    const wrapper = mount(OnboardingView, { global: { stubs: { teleport: true } } })
    await flushPromises()
    expect(wrapper.text()).toContain('Иванов')
    expect(wrapper.text()).toContain('Junior')
    expect(wrapper.findAll('thead th').map(x => x.text())).toEqual(['Этап / сотрудник', 'Иванов'])
    expect(wrapper.findAll('tbody th').map(x => x.text())).toEqual(['№', 'Грейд', 'NDA'])
    await wrapper.get('.cell-button').trigger('click')
    expect(wrapper.findComponent(OnboardingCellEditor).exists()).toBe(true)
    wrapper.unmount()
  })
  it('viewer edits cells but cannot configure the table', async () => {
    mock.editable = false
    const wrapper = mount(OnboardingView, { global: { stubs: { teleport: true } } })
    await flushPromises()
    expect(wrapper.text()).toContain('Иванов')
    expect(wrapper.text()).not.toContain('Настроить этапы')
    expect(wrapper.text()).not.toContain('Добавить сотрудника')
    expect(wrapper.text()).toContain('Скачать Excel')
    await wrapper.get('.cell-button').trigger('click')
    expect(wrapper.findComponent(OnboardingCellEditor).exists()).toBe(true)
    wrapper.unmount()
  })
  it('downloads the full table and reports download errors', async () => {
    const wrapper = mount(OnboardingView)
    await flushPromises()
    const button = wrapper.findAll('button').find(item => item.text() === 'Скачать Excel')!
    await button.trigger('click')
    await flushPromises()
    expect(mock.downloadOnboarding).toHaveBeenCalledOnce()

    mock.downloadOnboarding.mockRejectedValueOnce(new ApiError('Ошибка выгрузки', 500))
    await button.trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('Ошибка выгрузки')
    wrapper.unmount()
  })
  it('prevents duplicate downloads while the export is running', async () => {
    let finish!: () => void
    mock.downloadOnboarding.mockReturnValueOnce(new Promise<void>((resolve) => { finish = resolve }))
    const wrapper = mount(OnboardingView)
    await flushPromises()
    const button = wrapper.findAll('button').find(item => item.text() === 'Скачать Excel')!
    await button.trigger('click')
    await wrapper.vm.$nextTick()
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.text()).toBe('Скачивание…')
    finish()
    await flushPromises()
    expect(button.attributes('disabled')).toBeUndefined()
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
    await wrapper.get('select').setValue('completed')
    const dates = wrapper.findAll('input[type="date"]')
    expect((dates[1]!.element as HTMLInputElement).value).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    await dates[1]!.setValue('2026-09-19')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mock.saveCell).toHaveBeenCalledWith(1, 1, { version: 2, column_version: 1, planned_date: '2026-10-01', is_completed: true, is_not_required: false, completed_date: '2026-09-19' })
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
    await wrapper.get('button[aria-label="Переместить NDA вниз"]').trigger('click')
    await flushPromises()
    expect(mock.orderColumns).toHaveBeenCalledWith([{ id: 2, version: 1 }, { id: 1, version: 1 }])
    wrapper.unmount()
  })
})

describe('New onboarding states and clearing', () => {
  it('saves a dateless completion without sending dates', async () => {
    const wrapper = mount(OnboardingCellEditor, { props: { planId: 1, employeeName: 'Иванов', column: { ...column, field_type: 'checkbox' } }, global: { stubs: { teleport: true } } })
    await wrapper.get('select').setValue('completed')
    expect(wrapper.find('input[type="date"]').exists()).toBe(false)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mock.saveCell).toHaveBeenCalledWith(1, 1, { version: 0, column_version: 1, is_completed: true, is_not_required: false })
    wrapper.unmount()
  })
  it('keeps the planned date for not-required stages', async () => {
    const wrapper = mount(OnboardingCellEditor, { props: { planId: 1, employeeName: 'Иванов', column, cell }, global: { stubs: { teleport: true } } })
    await wrapper.get('select').setValue('not_required')
    expect(wrapper.get('input[type="date"]').attributes('disabled')).toBeDefined()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mock.saveCell).toHaveBeenCalledWith(1, 1, { version: 2, column_version: 1, planned_date: '2026-10-01', is_completed: false, is_not_required: true, completed_date: null })
    wrapper.unmount()
  })
  it('stages clearing until save and allows cancelling it', async () => {
    const wrapper = mount(OnboardingCellEditor, { props: { planId: 1, employeeName: 'Иванов', column, cell }, global: { stubs: { teleport: true } } })
    await wrapper.findAll('button').find(b => b.text() === 'Очистить ячейку')!.trigger('click')
    expect(mock.saveCell).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('будут очищены')
    await wrapper.findAll('button').find(b => b.text() === 'Отменить очистку')!.trigger('click')
    expect((wrapper.get('input[type="date"]').element as HTMLInputElement).value).toBe(cell.planned_date)
    await wrapper.findAll('button').find(b => b.text() === 'Очистить ячейку')!.trigger('click')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mock.saveCell).toHaveBeenCalledWith(1, 1, { version: 2, column_version: 1, clear: true })
    wrapper.unmount()
  })
  it('shows exemptions without completion or overdue styling', async () => {
    mock.plans.mockResolvedValueOnce({ items: [{ id: 1, full_name: 'Иванов', cells: { '1': { ...cell, planned_date: '2000-01-01', is_not_required: true } } }], total: 1, pages: 1 })
    const wrapper = mount(OnboardingView)
    await flushPromises()
    expect(wrapper.get('.not-required').text()).toBe('Не нужно')
    expect(wrapper.find('.overdue').exists()).toBe(false)
    expect(wrapper.find('.completed').exists()).toBe(false)
    wrapper.unmount()
  })
  it('marks completed cells for green background styling', async () => {
    mock.plans.mockResolvedValueOnce({ items: [{ id: 1, full_name: 'Иванов', cells: { '1': { ...cell, is_completed: true, completed_date: '2026-09-22' } } }], total: 1, pages: 1 })
    const wrapper = mount(OnboardingView)
    await flushPromises()
    expect(wrapper.get('td.completed').text()).toContain('✓')
    expect(wrapper.get('td.completed').classes()).not.toContain('not-required')
    wrapper.unmount()
  })
  it('supports creating a checkbox column', async () => {
    const wrapper = mount(OnboardingColumns, { props: { columns: [] } })
    await wrapper.get('input').setValue('Ознакомление')
    await wrapper.get('select').setValue('checkbox')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mock.createColumn).toHaveBeenCalledWith({ title: 'Ознакомление', field_type: 'checkbox' })
    wrapper.unmount()
  })
})

describe('Columns modal', () => {
  function modal() {
    const wrapper = mount(OnboardingColumnsModal, { props: { columns: [column] }, attachTo: document.body })
    const dom = new DOMWrapper(document.body)
    return { get: dom.get.bind(dom), findAll: dom.findAll.bind(dom), text: dom.text.bind(dom), emitted: wrapper.emitted.bind(wrapper), unmount: wrapper.unmount.bind(wrapper) }
  }
  it('opens from the table as a modal, not an inline panel', async () => {
    const wrapper = mount(OnboardingView, { global: { stubs: { teleport: true } } })
    await flushPromises()
    await wrapper.findAll('button').find(b => b.text() === 'Настроить этапы')!.trigger('click')
    expect(wrapper.get('[role="dialog"]').attributes('aria-modal')).toBe('true')
    expect(document.body.style.overflow).toBe('hidden')
    wrapper.unmount()
    expect(document.body.style.overflow).not.toBe('hidden')
  })
  it('protects dirty form on close, Escape and overlay clicks', async () => {
    const wrapper = modal()
    await wrapper.get('input').setValue('Не сохранено')
    await wrapper.get('.columns-overlay').trigger('click')
    expect(wrapper.emitted('close')).toBeUndefined()
    await wrapper.get('.columns-overlay').trigger('keydown', { key: 'Escape' })
    expect(wrapper.text()).toContain('несохранённые изменения')
    await wrapper.findAll('button').find(b => b.text() === 'Продолжить редактирование')!.trigger('click')
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('Не сохранено')
    await wrapper.get('button[aria-label="Закрыть настройку этапов"]').trigger('click')
    await wrapper.findAll('button').find(b => b.text() === 'Закрыть без сохранения')!.trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
    wrapper.unmount()
  })
  it('does not close during save and preserves input on errors', async () => {
    let reject!: (reason: unknown) => void
    mock.createColumn.mockImplementationOnce(() => new Promise((_resolve, fail) => { reject = fail }))
    const wrapper = modal()
    await wrapper.get('input').setValue('Новый')
    await wrapper.get('form').trigger('submit')
    await wrapper.get('.columns-overlay').trigger('keydown', { key: 'Escape' })
    expect(wrapper.emitted('close')).toBeUndefined()
    expect(wrapper.get('button[aria-label="Закрыть настройку этапов"]').attributes('disabled')).toBeDefined()
    reject(new ApiError('Ошибка сервера', 500))
    await flushPromises()
    expect(wrapper.text()).toContain('Ошибка сервера')
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('Новый')
    wrapper.unmount()
  })
  it('emits updates without closing and restores focus on unmount', async () => {
    const opener = document.createElement('button')
    document.body.appendChild(opener)
    opener.focus()
    const wrapper = modal()
    await wrapper.get('input').setValue('Новый')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.emitted('changed')).toHaveLength(1)
    expect(wrapper.emitted('close')).toBeUndefined()
    wrapper.unmount()
    expect(document.activeElement).toBe(opener)
    opener.remove()
  })
})
