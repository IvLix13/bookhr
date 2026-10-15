export type OnboardingFieldType = 'text' | 'date' | 'stage' | 'checkbox'
export interface OnboardingColumn {
  id: number
  title: string
  field_type: OnboardingFieldType
  document_stage_key?: string | null
  sort_order: number
  is_archived: boolean
  version: number
}
export interface OnboardingCell {
  version: number
  text_value: string | null
  date_value: string | null
  planned_date: string | null
  is_in_progress: boolean
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
  hire_date: string
  curator_name: string | null
  curator_employment_id?: number | null
  can_edit_cells?: boolean
  version: number
  cells: Record<string, OnboardingCell>
}

export interface OnboardingDeletePreview {
  version: number
  snapshot: string
  cell_count: number
  title?: string
  full_name?: string | null
  hire_date?: string
}
