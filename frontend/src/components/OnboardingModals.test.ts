import { DOMWrapper, enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/api/errors'
import OnboardingPlanModal from './OnboardingPlanModal.vue'
import OnboardingAddEmployeeModal from './OnboardingAddEmployeeModal.vue'
import OnboardingDeleteDialog from './OnboardingDeleteDialog.vue'
import OnboardingColumns from './OnboardingColumns.vue'
import type { OnboardingPlan, OnboardingColumn } from '@/types/onboarding'

const mocks = vi.hoisted(() => ({ plan: vi.fn(), savePlan: vi.fn(), employees: vi.fn(), create: vi.fn(), preview: vi.fn(), remove: vi.fn(), employeeRemove: vi.fn(), stages: vi.fn(), docx: vi.fn(), edit: true }))
vi.mock('@/api/client', () => ({ api: {
  onboardingDocumentStages: mocks.stages, downloadOnboardingDocx: mocks.docx,
  onboardingPlan: mocks.plan, updateOnboardingPlan: mocks.savePlan,
  employees: mocks.employees, createOnboardingPlan: mocks.create,
  onboardingDeletePreview: mocks.preview, deleteOnboarding: mocks.remove, deleteEmployeeWithPlan: mocks.employeeRemove,
} }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ canEdit: () => mocks.edit, user: { role: mocks.edit ? 'hr' : 'viewer', full_name: 'Иванов' } }) }))
enableAutoUnmount(afterEach)
afterEach(() => { vi.restoreAllMocks() })
const column: OnboardingColumn = { id: 4, title: 'NDA', field_type: 'checkbox', sort_order: 0, is_archived: false, version: 1 }
const plan: OnboardingPlan = { id: 1, employment_id: 2, full_name: 'Иванов', hire_date: '2026-10-10', employment_status: 'active', grade: 'Junior', curator_name: null, version: 1, cells: {} }
const preview = { version: 1, snapshot: 'a'.repeat(64), cell_count: 1, full_name: 'Иванов', hire_date: '2026-10-10' }
const dom = () => new DOMWrapper(document.body)
const button = (label: string) => dom().findAll('button').find(b => b.text() === label)!
beforeEach(() => {
  vi.resetAllMocks()
  mocks.edit = true
  mocks.stages.mockResolvedValue([{ key: 'nda', title: 'NDA' }])
  mocks.plan.mockResolvedValue({ ...plan })
  mocks.savePlan.mockResolvedValue({ ...plan, version: 2 })
  mocks.preview.mockResolvedValue(preview)
  mocks.remove.mockResolvedValue(undefined)
  mocks.employeeRemove.mockResolvedValue(undefined)
  mocks.employees.mockResolvedValue({ items: [{ id: 2, full_name: 'Иванов', hire_date: plan.hire_date, status: 'active' }], pages: 1 })
  mocks.create.mockResolvedValue(plan)
})

describe('Onboarding modal workflows with real Teleport', () => {
  it('closes only the menu on Escape, then closes the window on the next Escape', async () => {
    const root = mount(OnboardingPlanModal, { props: { planId: 1, columns: [column] } })
    await flushPromises()
    const toggle = dom().get('[aria-label="Действия с планом"]')
    await toggle.trigger('click')
    await dom().get('[aria-label="Поиск по таблице плана"]').trigger('keydown', { key: 'Escape' })
    expect(dom().find('.action-menu').exists()).toBe(false)
    expect(root.emitted('close')).toBeUndefined()
    await toggle.trigger('keydown', { key: 'Escape' })
    expect(root.emitted('close')).toHaveLength(1)
  })

  it('exports through the menu and prevents another export until completion', async () => {
    let finish!: () => void
    mocks.docx.mockReturnValue(new Promise<void>(resolve => { finish = resolve }))
    mount(OnboardingPlanModal, { props: { planId: 1, columns: [column] } })
    await flushPromises()
    const toggle = dom().get('[aria-label="Действия с планом"]')
    await toggle.trigger('click')
    await button('Выгрузить план').trigger('click')
    await toggle.trigger('click')
    expect(button('Выгрузка…').attributes('disabled')).toBeDefined()
    expect(mocks.docx).toHaveBeenCalledExactlyOnceWith(1)
    finish()
    await flushPromises()
    expect(button('Выгрузить план').attributes('disabled')).toBeUndefined()
  })

  it('initializes the column draft before observing its field type', async () => {
    const root = mount(OnboardingColumns, { props: { columns: [column] } })
    await flushPromises()
    expect(mocks.stages).toHaveBeenCalledTimes(1)
    expect(root.text()).toContain('Ответственный отдел')
    expect(root.text()).toContain('Соответствует этапу в документе')
    root.unmount()
  })

  it('loads the current plan and preserves dirty curator input on attempted close', async () => {
    const root = mount(OnboardingPlanModal, { props: { planId: 1, columns: [column] } })
    await flushPromises()
    expect(mocks.plan).toHaveBeenCalledWith(1)
    await dom().get('[aria-label="Действия с планом"]').trigger('click')
    await button('Изменить наставника').trigger('click')
    await dom().get('.curator-form input').setValue('Мой куратор')
    await dom().get('[aria-label="Закрыть окно"]').trigger('click')
    expect(root.emitted('close')).toBeUndefined()
    expect(dom().text()).toContain('несохранённые изменения')
    await button('Продолжить редактирование').trigger('click')
    expect((dom().get('.curator-form input').element as HTMLInputElement).value).toBe('Мой куратор')
    await dom().get('.curator-form').trigger('submit')
    await flushPromises()
    expect(mocks.savePlan).toHaveBeenCalledWith(1, { version: 1, curator_name: 'Мой куратор' })
    expect(root.emitted('close')).toBeUndefined()
  })

  it('keeps parent scroll locked and traps focus in the upper dialog', async () => {
    vi.spyOn(HTMLElement.prototype, 'offsetParent', 'get').mockReturnValue(document.body)
    const opener = document.createElement('button')
    document.body.appendChild(opener)
    opener.focus()
    const root = mount(OnboardingPlanModal, { props: { planId: 1, columns: [column] } })
    await flushPromises()
    await dom().get('[aria-label="Действия с планом"]').trigger('click')
    await button('Удалить план').trigger('click')
    await flushPromises()
    expect(document.body.style.overflow).toBe('hidden')
    const dialogs = dom().findAll('[role="dialog"]')
    expect(dialogs).toHaveLength(2)
    const cancel = button('Отмена')
    ;(cancel.element as HTMLElement).focus()
    await cancel.trigger('keydown', { key: 'Tab' })
    expect(dialogs[1]!.element.contains(document.activeElement)).toBe(true)
    expect(document.activeElement).toBe(dialogs[1]!.get('button').element)
    await cancel.trigger('click')
    expect(dom().findAll('[role="dialog"]')).toHaveLength(1)
    expect(document.body.style.overflow).toBe('hidden')
    root.unmount()
    expect(document.body.style.overflow).not.toBe('hidden')
    expect(document.activeElement).toBe(opener)
    opener.remove()
  })

  it('viewer sees own editable cells and no management actions', async () => {
    mocks.edit = false
    mount(OnboardingPlanModal, { props: { planId: 1, columns: [column] } })
    await flushPromises()
    expect(dom().find('.cell-button').exists()).toBe(true)
    await dom().get('[aria-label="Действия с планом"]').trigger('click')
    expect(dom().text()).not.toContain('Удалить план')
    expect(dom().text()).not.toContain('Изменить наставника')
  })

  it('restores the opener when a parent and its confirmation unmount together', async () => {
    vi.spyOn(HTMLElement.prototype, 'offsetParent', 'get').mockReturnValue(document.body)
    const opener = document.createElement('button')
    document.body.appendChild(opener)
    opener.focus()
    const root = mount(OnboardingPlanModal, { props: { planId: 1, columns: [column] } })
    await flushPromises()
    await dom().get('[aria-label="Действия с планом"]').trigger('click')
    await button('Изменить наставника').trigger('click')
    await dom().get('.curator-form input').setValue('Изменённый ввод')
    ;(dom().get('.curator-form input').element as HTMLElement).focus()
    await dom().get('[aria-label="Закрыть окно"]').trigger('click')
    await flushPromises()
    expect(dom().findAll('[role="dialog"]')).toHaveLength(2)
    root.unmount()
    expect(document.activeElement).toBe(opener)
    expect(document.body.style.overflow).not.toBe('hidden')
    opener.remove()
  })

  it('requires fresh confirmation after deletion conflicts and disables repeat clicks', async () => {
    mocks.remove.mockRejectedValueOnce(new ApiError('Данные изменились', 409))
    const root = mount(OnboardingDeleteDialog, { props: { kind: 'plans', id: 1, title: 'Удалить план' } })
    await flushPromises()
    await button('Подтвердить удаление').trigger('click')
    await flushPromises()
    expect(dom().text()).toContain('Данные изменились')
    expect(dom().findAll('button').some(b => b.text() === 'Подтвердить удаление')).toBe(false)
    expect(root.emitted('deleted')).toBeUndefined()
    await button('Обновить данные для подтверждения').trigger('click')
    await flushPromises()
    let finish!: () => void
    mocks.remove.mockReturnValueOnce(new Promise<void>(resolve => { finish = resolve }))
    await button('Подтвердить удаление').trigger('click')
    expect(button('Подтвердить удаление').attributes('disabled')).toBeDefined()
    await button('Подтвердить удаление').trigger('click')
    expect(mocks.remove).toHaveBeenCalledTimes(2)
    finish()
    await flushPromises()
    expect(root.emitted('deleted')).toHaveLength(1)
  })

  it('uses explicit employee-and-plan deletion rather than plan deletion', async () => {
    mount(OnboardingDeleteDialog, { props: { kind: 'plans', id: 1, employmentId: 2, title: 'Удалить сотрудника и план' } })
    await flushPromises()
    expect(dom().text()).toContain('Другие периоды трудоустройства сохранятся')
    await button('Подтвердить удаление').trigger('click')
    await flushPromises()
    expect(mocks.employeeRemove).toHaveBeenCalledWith(2, preview)
    expect(mocks.remove).not.toHaveBeenCalled()
  })

  it('removes a field only after confirmation and resets its edit form', async () => {
    const root = mount(OnboardingColumns, { props: { columns: [column] }, attachTo: document.body })
    await dom().get('[aria-label="Изменить NDA"]').trigger('click')
    await dom().get('[aria-label="Удалить NDA"]').trigger('click')
    await flushPromises()
    expect(mocks.remove).not.toHaveBeenCalled()
    await button('Подтвердить удаление').trigger('click')
    await flushPromises()
    expect(mocks.remove).toHaveBeenCalledWith('columns', 4, preview)
    expect((root.get('input').element as HTMLInputElement).value).toBe('')
    expect(root.emitted('changed')).toHaveLength(1)
  })

  it('preserves employee search on 409 and emits the created plan only once', async () => {
    const root = mount(OnboardingAddEmployeeModal)
    await flushPromises()
    await dom().get('input').setValue('Иванов')
    await dom().get('form').trigger('submit')
    await flushPromises()
    mocks.create.mockRejectedValueOnce(new ApiError('План уже существует', 409))
    await button('Создать план').trigger('click')
    await flushPromises()
    expect(dom().text()).toContain('План уже существует')
    expect((dom().get('input').element as HTMLInputElement).value).toBe('Иванов')
    let finish!: (value: OnboardingPlan) => void
    mocks.create.mockReturnValueOnce(new Promise<OnboardingPlan>(resolve => { finish = resolve }))
    await button('Создать план').trigger('click')
    await button('Создать план').trigger('click')
    expect(button('Отмена').attributes('disabled')).toBeDefined()
    finish(plan)
    await flushPromises()
    expect(root.emitted('created')).toEqual([[plan]])
    expect(mocks.create).toHaveBeenCalledTimes(2)
  })

  it('ignores stale employee searches and results after closing', async () => {
    let finish!: (value: unknown) => void
    mocks.employees.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
    const root = mount(OnboardingAddEmployeeModal)
    await dom().get('input').setValue('Иванов')
    await dom().get('form').trigger('submit')
    await flushPromises()
    finish({ items: [{ id: 3, full_name: 'Устаревший' }], pages: 1 })
    await flushPromises()
    expect(dom().text()).not.toContain('Устаревший')
    root.unmount()
    expect(document.body.style.overflow).not.toBe('hidden')
  })
})
