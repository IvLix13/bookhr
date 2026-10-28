import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import Details from './OnboardingPlanDetails.vue'
import type { OnboardingColumn, OnboardingPlan } from '@/types/onboarding'
const columns: OnboardingColumn[] = [
  { id: 1, title: 'Пропуск', responsible_department: 'Охрана', field_type: 'stage', version: 1, sort_order: 0, is_archived: false },
  { id: 2, title: 'Отдел', field_type: 'text', version: 1, sort_order: 1, is_archived: false },
]
const plan: OnboardingPlan = { id: 1, employment_id: 1, full_name: 'Иванов', grade: null, curator_name: null, hire_date: '2026-10-01', version: 1, employment_status: 'active', cells: {
  '1': { version: 1, text_value: null, date_value: null, planned_date: '2026-10-15', completed_date: '2026-10-14', is_completed: true, is_in_progress: false, is_not_required: false },
  '2': { version: 1, text_value: 'Разработка', date_value: null, planned_date: null, completed_date: null, is_completed: false, is_in_progress: false, is_not_required: false },
} }
describe('Plan table search and states', () => {
  it('searches visible labels, dates and values without changing row identity', async () => {
    const w = mount(Details, { props: { plan, columns, today: '2026-10-28', editable: true } })
    for (const q of [' охрана ', 'ВЫПОЛНЕНО', '14 октября 2026', 'Пропуск']) {
      await w.get('input').setValue(q)
      expect(w.findAll('tbody tr')).toHaveLength(1)
      expect(w.get('tbody th').text()).toBe('Пропуск')
    }
    await w.get('input').setValue('разработка')
    await w.get('.cell-button').trigger('click')
    expect(w.emitted('edit')?.[0]).toEqual([columns[1]])
    await w.get('input').setValue('нет совпадения')
    expect(w.text()).toContain('Ничего не найдено')
    await w.setProps({ plan: { ...plan, cells: { ...plan.cells, '2': { ...plan.cells['2']!, text_value: 'нет совпадения' } } } })
    expect(w.findAll('tbody tr')).toHaveLength(1)
    expect(w.get('input').element.value).toBe('нет совпадения')
  })
  it('highlights the completed row and gives exemption priority', async () => {
    const w = mount(Details, { props: { plan, columns, today: '2026-10-28', editable: false } })
    expect(w.findAll('tr.row-completed')).toHaveLength(1)
    expect(w.findAll('thead th').at(-1)?.text()).toBe('Состояние / значение')
    await w.setProps({ plan: { ...plan, cells: { ...plan.cells, '1': { ...plan.cells['1']!, is_not_required: true } } } })
    expect(w.find('tr.row-completed').exists()).toBe(false)
    expect(w.text()).toContain('Не нужно')
  })
})
