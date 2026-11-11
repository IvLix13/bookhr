import { describe, expect, it } from 'vitest'
import { planSummary, sortOnboardingColumns, stageState } from './onboarding'
import type { OnboardingCell, OnboardingColumn, OnboardingPlan } from '@/types/onboarding'
const empty: OnboardingCell = { version: 1, text_value: null, date_value: null, planned_date: null, completed_date: null, is_completed: false, is_not_required: false, is_in_progress: false }
const stage: OnboardingColumn = { id: 1, title: 'NDA', field_type: 'stage', sort_order: 1, is_archived: false, version: 1 }
const plan: OnboardingPlan = { id: 1, employment_id: 1, full_name: 'Иванов', grade: 'Junior', employment_status: 'active', hire_date: '2026-10-01', curator_name: null, version: 1, cells: {} }
describe('Onboarding summary', () => {
  it('sorts configuration by sort_order and ID without changing incoming array', () => {
    const unsorted = [{ ...stage, id: 9, sort_order: 3 }, { ...stage, id: 2, sort_order: 1 }, { ...stage, id: 3, sort_order: 1 }, { ...stage, id: 1, sort_order: 0 }]
    expect(sortOnboardingColumns(unsorted).map(column => column.id)).toEqual([1, 2, 3, 9])
    expect(unsorted.map(column => column.id)).toEqual([9, 2, 3, 1])
  })

  it('counts completed, in-progress and overdue required stages separately', () => {
    const columns = [stage, { ...stage, id: 2 }, { ...stage, id: 3 }, { ...stage, id: 4 }, { ...stage, id: 5, field_type: 'checkbox' as const }, { ...stage, id: 6, field_type: 'text' as const }, { ...stage, id: 7, is_archived: true }]
    const summary = planSummary({ ...plan, cells: {
      1: { ...empty, is_completed: true }, 2: { ...empty, is_in_progress: true, planned_date: '2026-10-09' },
      3: { ...empty, is_in_progress: true, planned_date: '2026-10-10' }, 4: { ...empty, is_not_required: true },
      6: { ...empty, text_value: 'Текст' }, 7: { ...empty, is_completed: true },
    } }, columns, '2026-10-10')
    expect(summary.total).toBe(4)
    expect(summary.percent).toBe(25)
    expect(summary.counts).toEqual({ completed: 1, in_progress: 2, overdue: 1 })
    expect(summary.next?.id).toBe(2)
  })
  it('does not count completed or exempt stages as overdue and handles no stages', () => {
    expect(stageState(stage, { ...empty, planned_date: '2000-01-01' }, '2026-10-10')).toBe('overdue')
    expect(stageState(stage, { ...empty, planned_date: '2026-10-10' }, '2026-10-10')).toBe('in_progress')
    expect(stageState(stage, { ...empty, planned_date: '2026-10-11' }, '2026-10-10')).toBe('in_progress')
    expect(stageState(stage, { ...empty }, '2026-10-10')).toBe('in_progress')
    expect(stageState({ ...stage, field_type: 'checkbox' }, { ...empty, planned_date: '2000-01-01' }, '2026-10-10')).toBe('in_progress')
    expect(stageState(stage, { ...empty, planned_date: '2000-01-01', is_completed: true }, '2026-10-10')).toBe('completed')
    expect(stageState(stage, { ...empty, planned_date: '2000-01-01', is_not_required: true }, '2026-10-10')).toBeNull()
    expect(planSummary(plan, [], '2026-10-10')).toMatchObject({ total: 0, percent: 0, next: null })
    expect(planSummary({ ...plan, cells: { 1: { ...empty, is_not_required: true } } }, [stage], '2026-10-10').percent).toBe(0)
  })
  it('uses existing department and start date fields, with hire date fallback', () => {
    const columns = [{ ...stage, id: 2, title: ' Отдел ', field_type: 'text' as const }, { ...stage, id: 3, title: 'Дата начала', field_type: 'date' as const }]
    expect(planSummary({ ...plan, cells: { 2: { ...empty, text_value: '11 отдел' }, 3: { ...empty, date_value: '2026-10-05' } } }, columns, '2026-10-10')).toMatchObject({ department: '11 отдел', arrival: '2026-10-05' })
    expect(planSummary(plan, columns, '2026-10-10').arrival).toBe(plan.hire_date)
  })
})
