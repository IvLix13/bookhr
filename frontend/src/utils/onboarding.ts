import type { OnboardingCell, OnboardingColumn, OnboardingPlan } from '@/types/onboarding'
import { formatShortDate } from '@/utils/dates'

export type StageState = 'completed' | 'in_progress' | 'overdue'
export function moscowToday() {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Moscow' }).format(new Date())
}
export function stageState(column: OnboardingColumn, cell: OnboardingCell | undefined, today: string): StageState | null {
  if (cell?.is_not_required) return null
  if (cell?.is_completed) return 'completed'
  if (column.field_type === 'stage' && cell?.planned_date && cell.planned_date < today) return 'overdue'
  return 'in_progress'
}
export const stageLabels: Record<StageState, string> = {
  completed: 'Выполнено', in_progress: 'В работе', overdue: 'Просрочено',
}
export function cellLabel(plan: OnboardingPlan, column: OnboardingColumn, today = moscowToday()) {
  const cell = plan.cells[column.id]
  if (cell?.is_not_required) return '—'
  if (column.field_type === 'text') return cell?.text_value || '—'
  if (column.field_type === 'date') return formatShortDate(cell?.date_value)
  const state = stageState(column, cell, today)!
  const date = column.field_type === 'stage' ? (cell?.is_completed ? cell.completed_date : cell?.planned_date) : null
  return date ? `${stageLabels[state]} · ${formatShortDate(date)}` : stageLabels[state]
}
export function planSummary(plan: OnboardingPlan, columns: OnboardingColumn[], today: string) {
  const active = columns.filter(c => !c.is_archived)
  const stages = active.filter(c => c.field_type === 'stage' || c.field_type === 'checkbox')
    .sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)
  const required = stages.filter(c => !plan.cells[c.id]?.is_not_required)
  const counts = { completed: 0, in_progress: 0, overdue: 0 }
  for (const column of required) {
    const state = stageState(column, plan.cells[column.id], today)
    if (state) counts[state]++
  }
  const remaining = required.filter(c => !plan.cells[c.id]?.is_completed).sort((a, b) => {
    const left = plan.cells[a.id]?.planned_date
    const right = plan.cells[b.id]?.planned_date
    return left && right ? left.localeCompare(right) || a.sort_order - b.sort_order || a.id - b.id : left ? -1 : right ? 1 : a.sort_order - b.sort_order || a.id - b.id
  })
  const department = active.find(c => c.field_type === 'text' && c.title.trim().toLocaleLowerCase('ru') === 'отдел')
  const start = active.find(c => c.field_type === 'date' && c.title.trim().toLocaleLowerCase('ru') === 'дата начала')
  return {
    counts, total: required.length,
    percent: required.length ? Math.round(counts.completed / required.length * 100) : 0,
    next: remaining[0] ?? null,
    department: department ? plan.cells[department.id]?.text_value : null,
    arrival: (start ? plan.cells[start.id]?.date_value : null) || plan.hire_date,
  }
}
