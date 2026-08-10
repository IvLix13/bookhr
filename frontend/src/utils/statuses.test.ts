import { describe, expect, it } from 'vitest'
import { getContractReportDisplayMeta, getEventStatusMeta, getPassportStatusMeta, getRewardStatusMeta } from '@/utils/statuses'

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

  it('maps reward statuses to Russian labels', () => {
    expect(getRewardStatusMeta('not_delivered')).toEqual({ label: 'Не вручено', variant: '' })
    expect(getRewardStatusMeta('in_hr')).toEqual({ label: 'В кадрах', variant: 'warning' })
    expect(getRewardStatusMeta('delivered')).toEqual({ label: 'Вручено', variant: 'success' })
  })

  it('maps contract report display statuses', () => {
    expect(getContractReportDisplayMeta('2026-08-01', 'completed', '2026-07-28')).toEqual({
      label: 'Выполнено',
      variant: 'success',
    })
    expect(getContractReportDisplayMeta('2026-08-01', 'planned', '2026-07-28')).toEqual({
      label: 'Срок не наступил',
      variant: '',
    })
    expect(getContractReportDisplayMeta('2026-07-01', 'planned', '2026-07-28')).toEqual({
      label: 'Запланировано',
      variant: 'warning',
    })
  })
})
