import { describe, expect, it } from 'vitest'
import { getEventStatusMeta, getPassportStatusMeta } from '@/utils/statuses'

describe('status dictionaries', () => {
  it('maps passport statuses to Russian labels', () => {
    expect(getPassportStatusMeta('ok')).toEqual({ label: 'Сделан', variant: 'success' })
    expect(getPassportStatusMeta('requires_preparation')).toEqual({
      label: 'Подготовить документы',
      variant: 'warning',
    })
    expect(getPassportStatusMeta('expired')).toEqual({ label: 'Просрочен', variant: 'danger' })
    expect(getPassportStatusMeta(null)).toEqual({ label: 'Не указан', variant: '' })
  })

  it('maps event statuses to Russian labels', () => {
    expect(getEventStatusMeta('planned')).toEqual({ label: 'Запланировано', variant: '' })
    expect(getEventStatusMeta('completed')).toEqual({ label: 'Выполнено', variant: 'success' })
    expect(getEventStatusMeta('cancelled')).toEqual({ label: 'Отменено', variant: 'warning' })
    expect(getEventStatusMeta('overdue')).toEqual({ label: 'Просрочено', variant: 'danger' })
  })
})
