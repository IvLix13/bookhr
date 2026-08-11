export const MODULE_LABELS = {
  calendar: 'Календарь',
  statistics: 'Статистика',
  employees: 'Сотрудники',
  import: 'Импорт',
  eventCreate: 'Создать мероприятие',
  contracts: 'Договоры',
  grades: 'Грейды',
  gradeCatalog: 'Справочник грейдов',
  rewards: 'Поощрения',
  awards: 'Награды за стаж',
  passports: 'Паспорта',
  events: 'Все мероприятия',
  settings: 'Настройки',
} as const

export const EVENT_TYPE_LABELS: Record<string, string> = {
  contract: 'Договор',
  grade: 'Грейд',
  award: 'Поощрение',
  report: 'Рапорт',
  passport: 'Паспорт',
  manual: 'Другое',
}

export const EVENT_SOURCE_LABELS: Record<string, string> = {
  manual: 'Вручную',
  rule_engine: 'Автоматически',
  import: 'Импорт',
}

export const IMPORT_STATUS_LABELS: Record<string, string> = {
  uploaded: 'Загружен',
  pending: 'Ожидает проверки',
  validated: 'Проверен',
  confirmed: 'Подтверждён',
  failed: 'Ошибка',
}

export const IMPORT_ACTION_LABELS: Record<string, string> = {
  create: 'Создать',
  update: 'Обновить',
  ambiguous: 'Дубликат',
  error: 'Ошибка',
  skip: 'Пропустить',
}

export const IMPORT_RESULT_LABELS: Record<string, string> = {
  created: 'Создан',
  updated: 'Обновлён',
  skipped: 'Пропущен',
  error: 'Ошибка',
}

export const IMPORT_SUMMARY_LABELS: Record<string, string> = {
  create: 'К созданию',
  update: 'К обновлению',
  ambiguous: 'Дубликаты',
  error: 'Ошибки проверки',
  created: 'Создано',
  updated: 'Обновлено',
  skipped: 'Пропущено',
  errors: 'Ошибки',
}

export const IMPORT_SKIP_REASON_LABELS: Record<string, string> = {
  ambiguous_unresolved: 'Не выбран дубликат',
  skipped_by_user: 'Пропущено вручную',
  no_hire_date: 'Нет даты начала работы',
  no_employment: 'Нет трудоустройства',
  no_person: 'Не выбран сотрудник',
  person_not_found: 'Сотрудник не найден',
  unknown_action: 'Неизвестное действие',
}

export function labelEventType(value: string | null | undefined): string {
  if (!value) return '—'
  return EVENT_TYPE_LABELS[value] ?? value
}

export function labelEventSource(value: string | null | undefined): string {
  if (!value) return '—'
  return EVENT_SOURCE_LABELS[value] ?? value
}

export function labelImportStatus(value: string | null | undefined): string {
  if (!value) return '—'
  return IMPORT_STATUS_LABELS[value] ?? value
}

export function labelImportAction(value: string | null | undefined): string {
  if (!value) return '—'
  return IMPORT_ACTION_LABELS[value] ?? value
}

export function labelImportResult(value: string | null | undefined): string {
  if (!value) return '—'
  return IMPORT_RESULT_LABELS[value] ?? value
}

export function labelImportSummaryKey(value: string): string {
  return IMPORT_SUMMARY_LABELS[value] ?? value
}

export function labelImportSkipReason(value: string): string {
  return IMPORT_SKIP_REASON_LABELS[value] ?? value
}

export const API_MESSAGE_LABELS: Record<string, string> = {
  'full_name and hire_date are required': 'Укажите ФИО и дату начала работы',
  'Import not validated': 'Импорт ещё не прошёл проверку',
  'Import failed': 'Импорт завершился с ошибкой',
  Forbidden: 'Недостаточно прав для выполнения действия',
  'Not found': 'Запись не найдена',
  'Invalid credentials': 'Неверный логин или пароль',
}

export function localizeApiMessage(message: string | undefined): string {
  if (!message) return 'Произошла ошибка'
  return API_MESSAGE_LABELS[message] ?? message
}
