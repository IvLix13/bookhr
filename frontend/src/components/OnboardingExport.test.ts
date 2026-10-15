import { DOMWrapper, enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import OnboardingPlanModal from './OnboardingPlanModal.vue'
import OnboardingColumns from './OnboardingColumns.vue'

const mocks = vi.hoisted(() => ({ plan: vi.fn(), export: vi.fn(), stages: vi.fn(), create: vi.fn() }))
vi.mock('@/api/client', () => ({ api: {
  onboardingPlan: mocks.plan, downloadOnboardingDocx: mocks.export,
  onboardingDocumentStages: mocks.stages, createOnboardingColumn: mocks.create,
} }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ canEdit: () => false, user: { role: 'viewer', full_name: 'Наставник' } }) }))
enableAutoUnmount(afterEach)
const dom = () => new DOMWrapper(document.body)
const button = (text: string) => dom().findAll('button').find(b => b.text() === text)!
beforeEach(() => {
  vi.resetAllMocks()
  mocks.plan.mockResolvedValue({ id: 1, full_name: 'Подопечный', grade: 'Junior', curator_name: 'Наставник', version: 1, cells: {}, can_edit_cells: true })
  mocks.export.mockResolvedValue(undefined)
  mocks.stages.mockResolvedValue([{ key: 'nda', title: 'NDA' }])
  mocks.create.mockResolvedValue({})
})
describe('DOCX export and mapping', () => {
  it('exports the open employee plan and allows the assigned mentor to edit cells', async () => {
    mount(OnboardingPlanModal, { props: { planId: 1, columns: [{ id: 4, title: 'Соглашение', field_type: 'stage', sort_order: 0, is_archived: false, version: 1 }] } })
    await flushPromises()
    expect(dom().find('.cell-button').exists()).toBe(true)
    expect(dom().text()).not.toContain('Изменить куратора')
    await button('Выгрузить план').trigger('click')
    await flushPromises()
    expect(mocks.export).toHaveBeenCalledWith(1)
  })
  it('shows download errors and enables retry', async () => {
    mocks.export.mockRejectedValueOnce(new Error('Шаблон не найден'))
    mount(OnboardingPlanModal, { props: { planId: 1, columns: [] } })
    await flushPromises()
    await button('Выгрузить план').trigger('click')
    await flushPromises()
    expect(dom().text()).toContain('Шаблон не найден')
    expect(button('Выгрузить план').attributes('disabled')).toBeUndefined()
  })
  it('sends the selected stable document stage key', async () => {
    const wrapper = mount(OnboardingColumns, { props: { columns: [] } })
    await flushPromises()
    await wrapper.get('input').setValue('Соглашение')
    await wrapper.findAll('select')[1]!.setValue('nda')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.create).toHaveBeenCalledWith({ title: 'Соглашение', field_type: 'stage', document_stage_key: 'nda' })
  })
})
