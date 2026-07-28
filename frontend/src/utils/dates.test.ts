import { describe, expect, it } from 'vitest'
import {
  defaultStatsPeriod,
  formatDisplayDate,
  formatLocalDate,
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
})
