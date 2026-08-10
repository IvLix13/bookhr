export type PassportStatus = 'ok' | 'requires_preparation' | 'expired'
export type EventStatus = 'planned' | 'completed' | 'cancelled' | 'overdue'
export type RewardStatus = 'not_delivered' | 'in_hr' | 'delivered'
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

const REWARD_STATUS_MAP: Record<RewardStatus, StatusMeta> = {
  not_delivered: { label: 'Не вручено', variant: '' },
  in_hr: { label: 'В кадрах', variant: 'warning' },
  delivered: { label: 'Вручено', variant: 'success' },
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

export function getRewardStatusMeta(status: string | null | undefined): StatusMeta {
  if (!status) return { label: '—', variant: '' }
  switch (status) {
    case 'not_delivered':
      return REWARD_STATUS_MAP.not_delivered
    case 'in_hr':
      return REWARD_STATUS_MAP.in_hr
    case 'delivered':
      return REWARD_STATUS_MAP.delivered
    default: {
      const _exhaustive: never = status as never
      return { label: String(_exhaustive), variant: '' }
    }
  }
}

export function getContractReportDisplayMeta(
  eventDate: string | null | undefined,
  eventStatus: string | null | undefined,
  todayIso: string,
): StatusMeta {
  if (!eventDate || !eventStatus) {
    return { label: '—', variant: '' }
  }

  if (eventStatus === 'completed') {
    return { label: 'Выполнено', variant: 'success' }
  }
  if (eventStatus === 'overdue') {
    return { label: 'Просрочено', variant: 'danger' }
  }
  if (eventStatus === 'planned' && eventDate > todayIso) {
    return { label: 'Срок не наступил', variant: '' }
  }
  if (eventStatus === 'planned') {
    return { label: 'Запланировано', variant: 'warning' }
  }

  return getEventStatusMeta(eventStatus)
}
