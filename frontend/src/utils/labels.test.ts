import { describe, expect, it } from 'vitest'
import {
  EVENT_TYPE_LABELS,
  labelEventType,
  labelImportAction,
  labelImportStatus,
  localizeApiMessage,
  MODULE_LABELS,
} from '@/utils/labels'

describe('labels', () => {
  it('maps known event types', () => {
    expect(labelEventType('contract')).toBe(EVENT_TYPE_LABELS.contract)
    expect(labelEventType('manual')).toBe('Другое')
  })

  it('falls back for unknown event types', () => {
    expect(labelEventType('unknown_type')).toBe('unknown_type')
  })

  it('maps import statuses and actions', () => {
    expect(labelImportStatus('validated')).toBe('Проверен')
    expect(labelImportAction('skip')).toBe('Пропустить')
  })

  it('localizes known API messages', () => {
    expect(localizeApiMessage('Forbidden')).toBe('Недостаточно прав для выполнения действия')
    expect(localizeApiMessage('grade name or rank must be unique')).toBe(
      'Название или ранг грейда должны быть уникальными',
    )
  })

  it('uses glossary module labels', () => {
    expect(MODULE_LABELS.events).toBe('Все мероприятия')
    expect(MODULE_LABELS.awards).toBe('Награды за стаж')
    expect(MODULE_LABELS.import).toBe('Импорт данных')
    expect(MODULE_LABELS.eventCreate).toBe('Создать мероприятие')
  })
})
