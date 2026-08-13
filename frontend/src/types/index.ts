export interface ApiResponse<T> {
  success: boolean
  message?: string
  data?: T
}

export interface Paginated<T> {
  items: T[]
  page: number
  per_page: number
  total: number
  pages: number
}

export interface User {
  id: number
  username: string
  full_name: string
  role: UserRole
}

export type UserRole = 'admin' | 'hr' | 'viewer'
export type AuthSource = 'local' | 'ldap'

export interface RoleItem {
  id: number
  name: UserRole
}

export interface UserListItem {
  id: number
  username: string
  full_name: string
  role: UserRole
  auth_source: AuthSource
  is_active: boolean
  is_locked: boolean
  failed_login_attempts: number
  locked_until: string | null
  created_at: string | null
  updated_at: string | null
}

export interface Employee {
  id: number
  person_uuid: string
  full_name: string | null
  title: string | null
  position_grade: Grade | null
  actual_grade: Grade | null
  grade_date: string | null
  eligible_date: string | null
  has_university: boolean
  hire_date: string
  status: string
  contract_end: string | null
  contract_days_left: number | null
  passport_until: string | null
  passport_status: string | null
  passport_days_left: number | null
  tenure_years: number
  reward_status: RewardStatus | null
}

export interface Grade {
  id: number
  name: string
  rank: number
  min_years: number
  is_active?: boolean
}

export interface EventItem {
  id: number
  title: string
  event_type: string
  description: string | null
  event_date: string
  status: string
  effective_status?: string
  source: string
  employment_id: number | null
  employee_name: string | null
  created_by: string | null
  created_at: string | null
  completed_at: string | null
  completion_comment: string | null
}

export interface ContractRow {
  id: number
  employment_id: number
  full_name: string | null
  start_date: string
  end_date: string
  days_left: number
  is_active: boolean
  renewal_report_event: {
    id: number
    event_date: string
    status: string
    effective_status?: string
  } | null
}

export type RewardStatus = 'not_delivered' | 'in_hr' | 'delivered'

export interface RewardRow {
  id: number
  employment_id: number
  full_name: string | null
  reward_type: string
  status: RewardStatus
  updated_at: string | null
  directive_text: string | null
  delivered_date: string | null
  notes: string | null
}

export interface GradeRow {
  employment_id: number
  full_name: string | null
  grade: Grade | null
  grade_date: string | null
  next_grade: Grade | null
  eligible_date: string | null
  days_left: number | null
}

export interface PassportRow {
  person_uuid: string
  employment_id: number | null
  full_name: string | null
  valid_until: string | null
  days_left: number | null
  status: string | null
}

export interface TenureRow {
  employment_id: number
  full_name: string | null
  tenure_years: number
  awards: Record<string, { milestone_years: number; milestone_date: string | null; is_received: boolean }>
}

export interface DashboardStats {
  period: { from: string; to: string }
  employees: { active: number; hired_in_period: number; dismissed_in_period: number }
  events: {
    planned: number
    overdue: number
    completed: number
    cancelled: number
    completion_rate: number
    by_type: Record<string, number>
    monthly: Array<{
      month: string
      total: number
      planned: number
      overdue: number
      completed: number
      cancelled: number
    }>
  }
  contracts: { active: number; expired: number; expiring_120d: number }
  grades: {
    distribution: Record<string, number>
    without_grade: number
    eligible_now: number
    eligible_30d: number
    assigned_in_period: number
  }
  tenure: {
    pending: Record<string, number>
    received: Record<string, number>
    received_in_period: number
  }
  passports: {
    ok: number
    requires_preparation: number
    expired: number
    missing: number
    expiring_90d: number
  }
}

export interface NotificationRule {
  id: number
  company_id: number | null
  event_type: string | null
  room_token: string
  room_name: string | null
  is_enabled: boolean
  remind_days_before: number
  repeat_interval_days: number
  overdue_interval_days: number
  escalation_room_token: string | null
  escalation_after_days: number | null
  send_time_moscow: string
}

export interface ImportCandidate {
  uuid: string
  full_name: string | null
  title?: string | null
}

export type ImportType = 'employees' | 'rewards'

export interface UnknownGrade {
  name: string
  count: number
}

export interface ImportRow {
  id: number
  row_number: number
  action: string | null
  person_uuid: string | null
  full_name?: string | null
  reward_type?: string | null
  candidates?: ImportCandidate[] | null
  errors: string[] | null
  warnings: string[] | null
  result?: string | null
  result_message?: string | null
}

export interface ImportSummaryCounts {
  create?: number
  update?: number
  ambiguous?: number
  error?: number
  created?: number
  updated?: number
  skipped?: number
  errors?: number
  skipped_reasons?: Record<string, number>
  [key: string]: number | Record<string, number> | undefined
}

export interface ImportJob {
  id: number
  filename: string
  import_type?: ImportType
  status: string
  summary: ImportSummaryCounts | null
  unknown_grades?: UnknownGrade[]
  error_message?: string | null
  created_at: string | null
  rows: ImportRow[]
}

export interface TableQueryState {
  page: number
  per_page: number
  q: string
  sort: string | null
  direction: 'asc' | 'desc'
  columnFilters: Record<string, string>
}

export interface SearchResult {
  id: number | string
  type: string
  title: string
  subtitle?: string | null
  route?: string | null
}

export interface SearchResponse {
  q: string
  results: SearchResult[]
  total: number
}

export type AttentionSeverity = 'info' | 'warning' | 'danger'

export interface AttentionItem {
  id: string
  category: string
  title: string
  subtitle?: string | null
  severity: AttentionSeverity
  route?: string | null
  count?: number
}

export interface AttentionSummary {
  total: number
  counts: Record<string, number>
  items: AttentionItem[]
}
