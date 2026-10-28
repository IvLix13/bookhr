import { DOMWrapper, enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import OnboardingView from '@/views/OnboardingView.vue'
import OnboardingCellEditor from '@/components/OnboardingCellEditor.vue'
import OnboardingColumns from '@/components/OnboardingColumns.vue'
import OnboardingColumnsModal from '@/components/OnboardingColumnsModal.vue'
import OnboardingPlanModal from '@/components/OnboardingPlanModal.vue'
import { ApiError } from '@/api/errors'
import type { OnboardingColumn } from '@/types/onboarding'

enableAutoUnmount(afterEach)

const mock = vi.hoisted(() => ({
  push: vi.fn(),
  editable: true,
  role: 'hr' as 'admin' | 'hr' | 'viewer',
  fullName: 'HR User',
  columns: vi.fn(), plans: vi.fn(), employees: vi.fn(), createPlan: vi.fn(),
  saveCell: vi.fn(), createColumn: vi.fn(), updateColumn: vi.fn(), orderColumns: vi.fn(),
  downloadOnboarding: vi.fn(), updatePlan: vi.fn(), plan: vi.fn(), preview: vi.fn(), remove: vi.fn(), removeEmployee: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mock.push }), useRoute: () => ({ query: {} }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({
  canEdit: () => mock.editable,
  user: { id: 1, username: 'user', full_name: mock.fullName, role: mock.role },
}) }))
vi.mock('@/api/client', () => ({ api: {
  onboardingColumns: mock.columns, onboardingPlans: mock.plans, employees: mock.employees,
  createOnboardingPlan: mock.createPlan, updateOnboardingCell: mock.saveCell,
  createOnboardingColumn: mock.createColumn, updateOnboardingColumn: mock.updateColumn,
  orderOnboardingColumns: mock.orderColumns,
  downloadOnboarding: mock.downloadOnboarding, updateOnboardingPlan: mock.updatePlan,
  onboardingPlan: mock.plan, onboardingDeletePreview: mock.preview, deleteOnboarding: mock.remove, deleteEmployeeWithPlan: mock.removeEmployee,
} }))
const column: OnboardingColumn = { id: 1, title: 'NDA', field_type: 'stage', sort_order: 0, is_archived: false, version: 1 }
const cell = { version: 2, text_value: null, date_value: null, planned_date: '2026-10-01', is_completed: false, is_in_progress: false, is_not_required: false, completed_date: null }

beforeEach(() => {
  vi.resetAllMocks()
  mock.editable = true
  mock.role = 'hr'
  mock.fullName = 'HR User'
  mock.columns.mockResolvedValue([{ ...column }])
  mock.plans.mockResolvedValue({ items: [{ id: 1, employment_id: 2, full_name: 'Иванов', grade: 'Junior', employment_status: 'active', hire_date: '2020-01-01', curator_name: null, version: 1, cells: { '1': { ...cell } } }], page: 1, per_page: 25, total: 1, pages: 1 })
  mock.plan.mockImplementation(async (id) => {
    const result = await mock.plans.mock.results.at(-1)?.value
    return result.items.find((plan: { id: number }) => plan.id === id) ?? result.items[0]
  })
  mock.preview.mockResolvedValue({ version: 1, snapshot: 'a'.repeat(64), cell_count: 1 })
  mock.remove.mockResolvedValue(undefined)
  mock.removeEmployee.mockResolvedValue(undefined)
  mock.employees.mockResolvedValue({ items: [{ id: 2, full_name: 'Петров', hire_date: '2020-01-01', status: 'active' }], page: 1, pages: 1, total: 1 })
  mock.createPlan.mockResolvedValue({ id: 2 })
  mock.saveCell.mockResolvedValue({ ...cell, version: 3 })
  mock.createColumn.mockResolvedValue({ ...column, id: 2 })
  mock.updateColumn.mockResolvedValue({ ...column, version: 2 })
  mock.orderColumns.mockResolvedValue([])
  mock.downloadOnboarding.mockResolvedValue(undefined)
})

describe('Onboarding cards', () => {
  it('returns to the last valid page after deleting its final plan and preserves search', async () => {
    const first = { id: 1, full_name: 'Иванов', cells: {} }
    const second = { id: 2, full_name: 'Иванов Второй', cells: {} }
    mock.plans.mockResolvedValueOnce({ items: [first], total: 26, pages: 2 })
      .mockResolvedValueOnce({ items: [second], total: 26, pages: 2 })
      .mockResolvedValueOnce({ items: [], total: 25, pages: 1 })
      .mockResolvedValueOnce({ items: [first], total: 25, pages: 1 })
    const wrapper = mount(OnboardingView, { global: { stubs: { teleport: true } } })
    await flushPromises()
    await wrapper.get('input[aria-label="Поиск планов по ФИО"]').setValue('Иванов')
    await wrapper.findAll('button').find(b => b.text() === 'Далее')!.trigger('click')
    await flushPromises()
    await wrapper.get('.expand-button').trigger('click')
    await flushPromises()
    wrapper.getComponent(OnboardingPlanModal).vm.$emit('deleted')
    await flushPromises()
    expect(mock.plans).toHaveBeenLastCalledWith({ page: 1, per_page: 25, q: 'Иванов' })
    expect(wrapper.findComponent(OnboardingPlanModal).exists()).toBe(false)
    expect(wrapper.text()).toContain('Всего: 25')
  })
  it('renders employee cards and expands the selected plan to edit its stages', async () => {
    mock.columns.mockResolvedValueOnce([column, { ...column, id: 2, title: 'Пропуск', field_type: 'checkbox' }, { ...column, id: 3, title: 'Архив', is_archived: true }])
    mock.plans.mockResolvedValueOnce({ items: [
      { id: 10, full_name: 'Иванов', grade: 'Junior', cells: { '1': cell } },
      { id: 20, full_name: 'Петров', grade: 'Senior', cells: { '2': { ...cell, is_completed: true } } },
    ], total: 2, pages: 1 })
    const wrapper = mount(OnboardingView, { global: { stubs: { teleport: true } } })
    await flushPromises()
    expect(wrapper.findAll('.plan-card h3').map(x => x.text())).toEqual(['Иванов', 'Петров'])
    expect(wrapper.find('table').exists()).toBe(false)
    await wrapper.findAll('.expand-button')[1]!.trigger('click')
    await flushPromises()
    expect(wrapper.findAll('tbody th').map(x => x.text())).toEqual(['NDA', 'Пропуск'])
    expect(wrapper.text()).not.toContain('Архив')
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
    await wrapper.get('.expand-button').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('tbody th').map(x => x.text())).toEqual(['NDA'])
    await wrapper.get('.cell-button').trigger('click')
    expect(wrapper.findComponent(OnboardingCellEditor).exists()).toBe(true)
    wrapper.unmount()
  })
  it('viewer edits only the employee with the same name and cannot configure the table', async () => {
    mock.editable = false
    mock.role = 'viewer'
    mock.fullName = '  иванов '
    mock.plans.mockResolvedValueOnce({ items: [
      { id: 10, full_name: 'Иванов', grade: 'Junior', cells: { '1': cell } },
      { id: 20, full_name: 'Петров', grade: 'Senior', cells: { '1': cell } },
    ], total: 2, pages: 1 })
    const wrapper = mount(OnboardingView, { global: { stubs: { teleport: true } } })
    await flushPromises()
    expect(wrapper.text()).not.toContain('Настроить этапы')
    expect(wrapper.text()).not.toContain('Добавить сотрудника')
    expect(wrapper.text()).toContain('Скачать Excel')
    await wrapper.findAll('.expand-button')[0]!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).not.toContain('Изменить наставника')
    expect(wrapper.findAll('.cell-button').map(button => button.attributes('aria-label'))).toEqual(['NDA, Иванов: 1 октября 2026 г.'])
    expect(wrapper.text()).toContain('Петров')
    await wrapper.get('.cell-button').trigger('click')
    expect(wrapper.getComponent(OnboardingCellEditor).props('planId')).toBe(10)
    wrapper.unmount()
  })
  it('downloads the full table and reports download errors', async () => {
    const wrapper = mount(OnboardingView, { global: { stubs: { teleport: true } } })
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
    const wrapper = mount(OnboardingView, { global: { stubs: { teleport: true } } })
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
  it('searches plans and opens the creation wizard', async () => {
    const wrapper = mount(OnboardingView, { global: { stubs: { teleport: true } } })
    await flushPromises()
    await wrapper.get('input[aria-label="Поиск планов по ФИО"]').setValue('Иванов')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mock.plans).toHaveBeenLastCalledWith({ q: 'Иванов', page: 1, per_page: 25 })
    await wrapper.findAll('button').find(b => b.text() === 'Создать план')!.trigger('click')
    expect(mock.push).toHaveBeenCalledWith({ name: 'onboarding-create' })
    expect(mock.createPlan).not.toHaveBeenCalled()

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
    expect(mock.saveCell).toHaveBeenCalledWith(1, 1, { version: 2, column_version: 1, planned_date: '2026-10-01', is_completed: true, is_in_progress: false, is_not_required: false, completed_date: '2026-09-19' })
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
    expect(mock.createColumn).toHaveBeenCalledWith({ title: 'Отдел', field_type: 'text', responsible_department: null, document_stage_key: null })
    await wrapper.get('button[aria-label="Архивировать NDA"]').trigger('click')
    expect(mock.updateColumn).not.toHaveBeenCalled()
    await wrapper.get('button[aria-label="Подтвердить архивирование"]').trigger('click')
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
    expect(mock.saveCell).toHaveBeenCalledWith(1, 1, { version: 0, column_version: 1, is_completed: true, is_in_progress: false, is_not_required: false })
    wrapper.unmount()
  })
  it('keeps the planned date for not-required stages', async () => {
    const wrapper = mount(OnboardingCellEditor, { props: { planId: 1, employeeName: 'Иванов', column, cell }, global: { stubs: { teleport: true } } })
    await wrapper.get('select').setValue('not_required')
    expect(wrapper.get('input[type="date"]').attributes('disabled')).toBeDefined()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mock.saveCell).toHaveBeenCalledWith(1, 1, { version: 2, column_version: 1, planned_date: '2026-10-01', is_completed: false, is_in_progress: false, is_not_required: true, completed_date: null })
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
    const wrapper = mount(OnboardingView, { global: { stubs: { teleport: true } } })
    await flushPromises()
    await wrapper.get('.expand-button').trigger('click')
    await flushPromises()
    expect(wrapper.get('.not-required').text()).toBe('Не нужно')
    expect(wrapper.find('.overdue').exists()).toBe(false)
    expect(wrapper.find('.completed').exists()).toBe(false)
    wrapper.unmount()
  })
  it('marks completed cells for green background styling', async () => {
    mock.plans.mockResolvedValueOnce({ items: [{ id: 1, full_name: 'Иванов', cells: { '1': { ...cell, is_completed: true, completed_date: '2026-09-22' } } }], total: 1, pages: 1 })
    const wrapper = mount(OnboardingView, { global: { stubs: { teleport: true } } })
    await flushPromises()
    await wrapper.get('.expand-button').trigger('click')
    await flushPromises()
    expect(wrapper.get('td.completed').text()).toContain('Выполнено')
    expect(wrapper.get('td.completed').classes()).not.toContain('not-required')
    wrapper.unmount()
  })
  it('supports creating a checkbox column', async () => {
    const wrapper = mount(OnboardingColumns, { props: { columns: [] } })
    await wrapper.get('input').setValue('Ознакомление')
    await wrapper.get('select').setValue('checkbox')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mock.createColumn).toHaveBeenCalledWith({ title: 'Ознакомление', field_type: 'checkbox', responsible_department: null, document_stage_key: null })
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

describe('Card interactions', () => {
  it('saves the curator and keeps the plan modal open after refresh', async () => {
    const root = mount(OnboardingView, { attachTo: document.body })
    const dom = new DOMWrapper(document.body)
    const wrapper = { get: dom.get.bind(dom), find: dom.find.bind(dom), findAll: dom.findAll.bind(dom), unmount: root.unmount.bind(root) }
    await flushPromises()
    await wrapper.get('.expand-button').trigger('click')
    await flushPromises()
    await wrapper.get('[aria-label="Действия с планом"]').trigger('click')
    await wrapper.findAll('button').find(b => b.text() === 'Изменить наставника')!.trigger('click')
    await wrapper.get('.curator-form input').setValue('  Петров Пётр  ')
    await wrapper.get('.curator-form').trigger('submit')
    await flushPromises()
    expect(mock.updatePlan).toHaveBeenCalledWith(1, { version: 1, curator_name: 'Петров Пётр' })
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    expect(wrapper.find('.curator-form').exists()).toBe(false)
    wrapper.unmount()
  })
  it('keeps curator input on conflict and blocks stale retry', async () => {
    mock.updatePlan.mockRejectedValueOnce(new ApiError('Конфликт', 409))
    const root = mount(OnboardingView, { attachTo: document.body })
    const dom = new DOMWrapper(document.body)
    const wrapper = { get: dom.get.bind(dom), find: dom.find.bind(dom), findAll: dom.findAll.bind(dom), unmount: root.unmount.bind(root) }
    await flushPromises()
    await wrapper.get('.expand-button').trigger('click')
    await flushPromises()
    await wrapper.get('[aria-label="Действия с планом"]').trigger('click')
    await wrapper.findAll('button').find(b => b.text() === 'Изменить наставника')!.trigger('click')
    await wrapper.get('.curator-form input').setValue('Мой ввод')
    await wrapper.get('.curator-form').trigger('submit')
    await flushPromises()
    expect((wrapper.get('.curator-form input').element as HTMLInputElement).value).toBe('Мой ввод')
    expect(wrapper.get('.curator-form button').attributes('disabled')).toBeDefined()
    await wrapper.get('.curator-form').trigger('submit')
    expect(mock.updatePlan).toHaveBeenCalledOnce()
    wrapper.unmount()
  })
  it('saves an explicit in-progress state with dates preserved', async () => {
    const wrapper = mount(OnboardingCellEditor, { props: { planId: 1, employeeName: 'Иванов', column, cell }, global: { stubs: { teleport: true } } })
    await wrapper.get('select').setValue('in_progress')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mock.saveCell).toHaveBeenCalledWith(1, 1, { version: 2, column_version: 1, planned_date: '2026-10-01', is_completed: false, is_in_progress: true, is_not_required: false, completed_date: null })
    wrapper.unmount()
  })
})
