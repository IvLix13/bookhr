export type PassportStatus = 'ok' | 'requires_preparation' | 'expired'
export type EventStatus = 'planned' | 'completed' | 'cancelled' | 'overdue'
export type BadgeVariant = '' | 'success' | 'warning' | 'danger'

export interface StatusMeta {
  label: string
  variant: BadgeVariant
}

const PASSPORT_STATUS_MAP: Record<PassportStatus, StatusMeta> = {
  ok: { label: 'Сделан', variant: 'success' },
  requires_preparation: { label: 'Подготовить документы', variant: 'warning' },
  expired: { label: 'Просрочен', variant: 'danger' },
}

const EVENT_STATUS_MAP: Record<EventStatus, StatusMeta> = {
  planned: { label: 'Запланировано', variant: '' },
  completed: { label: 'Выполнено', variant: 'success' },
  cancelled: { label: 'Отменено', variant: 'warning' },
  overdue: { label: 'Просрочено', variant: 'danger' },
}

const PASSPORT_STATUS_UNKNOWN: StatusMeta = {
  label: 'Не указан',
  variant: '',
}

export function getPassportStatusMeta(status: string | null | undefined): StatusMeta {
  if (!status) return PASSPORT_STATUS_UNKNOWN
  if (status in PASSPORT_STATUS_MAP) {
    return PASSPORT_STATUS_MAP[status as PassportStatus]
  }
  return { label: status, variant: '' }
}

export function getEventStatusMeta(status: string | null | undefined): StatusMeta {
  if (!status) return { label: '—', variant: '' }
  if (status in EVENT_STATUS_MAP) {
    return EVENT_STATUS_MAP[status as EventStatus]
  }
  return { label: status, variant: '' }
}
