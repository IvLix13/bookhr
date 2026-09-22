export type OnboardingFieldType = 'text' | 'date' | 'stage' | 'checkbox'
export interface OnboardingColumn {
  id: number
  title: string
  field_type: OnboardingFieldType
  sort_order: number
  is_archived: boolean
  version: number
}
export interface OnboardingCell {
  version: number
  text_value: string | null
  date_value: string | null
  planned_date: string | null
  is_completed: boolean
  is_not_required: boolean
  completed_date: string | null
}
export interface OnboardingPlan {
  id: number
  employment_id: number
  full_name: string | null
  grade: string | null
  employment_status: string
  cells: Record<string, OnboardingCell>
}
