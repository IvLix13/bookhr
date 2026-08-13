import { describe, expect, it } from 'vitest'
import {
  attentionCategoryRoute,
  attentionEventId,
  attentionItemKey,
  eventDetailLocation,
  resolveAttentionRoute,
  staysOnCalendar,
} from '@/utils/attention'

describe('attention utils', () => {
  it('builds stable item keys', () => {
    expect(attentionItemKey({ category: 'events', id: 5, title: 'x', severity: 'danger' })).toBe(
      'events-5',
    )
  })

  it('opens event details on the calendar instead of the events tab', () => {
    expect(
      resolveAttentionRoute({
        category: 'events',
        id: 12,
        title: 'Test',
        severity: 'warning',
      }),
    ).toEqual({ name: 'calendar', query: { event: '12' } })
    expect(eventDetailLocation(12)).toEqual({ name: 'calendar', query: { event: '12' } })
  })

  it('opens grade-related items on the calendar via linked event', () => {
    const item = {
      category: 'grades',
      id: 88,
      title: 'Иван Иванов',
      severity: 'warning' as const,
      route: '/?event=88',
    }
    expect(staysOnCalendar(item)).toBe(true)
    expect(attentionEventId(item)).toBe(88)
    expect(resolveAttentionRoute(item)).toEqual({ name: 'calendar', query: { event: '88' } })
  })

  it('keeps grade items on the calendar even without a linked event', () => {
    const item = {
      category: 'grades',
      id: 3,
      title: 'Иван Иванов',
      severity: 'warning' as const,
      route: '/grades',
    }
    expect(staysOnCalendar(item)).toBe(true)
    expect(resolveAttentionRoute(item)).toEqual({ name: 'calendar' })
  })

  it('treats backend /events route as a calendar event even without category', () => {
    expect(
      staysOnCalendar({
        category: 'other',
        id: 9,
        title: 'Legacy',
        severity: 'danger',
        route: '/events',
      }),
    ).toBe(true)
    expect(
      resolveAttentionRoute({
        category: 'other',
        id: 9,
        title: 'Legacy',
        severity: 'danger',
        route: '/events',
      }),
    ).toEqual({ name: 'calendar', query: { event: '9' } })
  })

  it('keeps the events and grades category chips on the calendar', () => {
    expect(attentionCategoryRoute('events')).toEqual({ name: 'calendar' })
    expect(attentionCategoryRoute('grades')).toEqual({ name: 'calendar' })
    expect(attentionCategoryRoute('tenure')).toBe('/awards')
    expect(attentionCategoryRoute('contracts')).toBe('/contracts')
  })
})
