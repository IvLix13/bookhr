import { describe, expect, it } from 'vitest'
import {
  addYearsToIsoDate,
  calculateTermYears,
  defaultStatsPeriod,
  formatDisplayDate,
  formatLocalDate,
  formatMonthYearLabel,
  formatNumericDate,
  formatShortDate,
  isSameLocalDate,
  monthRange,
  parseIsoDate,
} from '@/utils/dates'

describe('dates utils', () => {
  it('formats local date without UTC shift', () => {
    const value = new Date(2026, 6, 24)
    expect(formatLocalDate(value)).toBe('2026-07-24')
  })

  it('builds month range in local timezone', () => {
    expect(monthRange(new Date(2026, 6, 15))).toEqual({
      from: '2026-07-01',
      to: '2026-07-31',
    })
  })

  it('builds default stats period', () => {
    const period = defaultStatsPeriod()
    expect(period.from <= period.to).toBe(true)
  })

  it('formats display date in Russian locale', () => {
    expect(formatDisplayDate('2026-07-24')).toContain('2026')
  })

  it('formats numeric date as DD.MM.YYYY', () => {
    expect(formatNumericDate('2026-07-24')).toBe('24.07.2026')
    expect(formatNumericDate(null)).toBe('—')
  })

  it('formats month year label with lowercase г.', () => {
    expect(formatMonthYearLabel(new Date(2026, 6, 1))).toBe('Июль 2026 г.')
    expect(formatMonthYearLabel(new Date(2026, 0, 1))).toBe('Январь 2026 г.')
  })

  it('formats short date as DD month YYYY г.', () => {
    expect(formatShortDate('2026-07-24')).toBe('24 июля 2026 г.')
    expect(formatShortDate(null)).toBe('—')
  })

  it('parses iso date for sorting', () => {
    expect(parseIsoDate('2026-07-24')).toBe(20260724)
    expect(parseIsoDate(null)).toBeNull()
  })

  it('compares local dates', () => {
    expect(isSameLocalDate(new Date(2026, 6, 24), new Date(2026, 6, 24))).toBe(true)
  })

  it('adds years to iso date', () => {
    expect(addYearsToIsoDate('2024-09-01', 1)).toBe('2025-09-01')
    expect(addYearsToIsoDate('2024-09-01', 2)).toBe('2026-09-01')
  })

  it('calculates term years between dates', () => {
    expect(calculateTermYears('2024-09-01', '2025-09-01')).toBe(1)
    expect(calculateTermYears('2024-09-01', '2026-09-01')).toBe(2)
    expect(calculateTermYears('2024-09-01', '2026-03-01')).toBe(1.5)
    expect(calculateTermYears('2024-09-01', '2027-09-01')).toBe(3)
    expect(calculateTermYears('2024-09-01', '2029-09-01')).toBe(5)
    expect(calculateTermYears('2024-09-01', '2024-09-01')).toBeNull()
    expect(calculateTermYears('2024-09-01', '2023-09-01')).toBeNull()
  })
})
