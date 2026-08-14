import { describe, expect, it } from 'vitest'
import {
  attentionCategoryRoute,
  attentionEventId,
  attentionItemKey,
  canOpenAttentionEvent,
  eventDetailLocation,
  resolveAttentionRoute,
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

  it('opens grade-related items via their linked event', () => {
    const item = {
      category: 'grades',
      id: 88,
      title: 'Иван Иванов',
      severity: 'warning' as const,
      route: '/?event=88',
    }
    expect(canOpenAttentionEvent(item)).toBe(true)
    expect(attentionEventId(item)).toBe(88)
    expect(resolveAttentionRoute(item)).toEqual({ name: 'calendar', query: { event: '88' } })
  })

  it('prefers the event id reported by the backend', () => {
    const item = {
      category: 'contracts',
      id: 4,
      title: 'Иван Иванов',
      severity: 'warning' as const,
      route: '/contracts',
      event_id: 71,
    }
    expect(canOpenAttentionEvent(item)).toBe(true)
    expect(attentionEventId(item)).toBe(71)
    expect(resolveAttentionRoute(item)).toEqual({ name: 'calendar', query: { event: '71' } })
  })

  it('navigates to the module when no event backs the item', () => {
    const item = {
      category: 'grades',
      id: 3,
      title: 'Иван Иванов',
      severity: 'warning' as const,
      route: '/grades',
    }
    expect(canOpenAttentionEvent(item)).toBe(false)
    expect(resolveAttentionRoute(item)).toBe('/grades')
  })

  it('treats a backend /events route as an event even without category', () => {
    const item = {
      category: 'other',
      id: 9,
      title: 'Legacy',
      severity: 'danger' as const,
      route: '/events',
    }
    expect(canOpenAttentionEvent(item)).toBe(true)
    expect(resolveAttentionRoute(item)).toEqual({ name: 'calendar', query: { event: '9' } })
  })

  it('keeps the events and grades category chips on the calendar', () => {
    expect(attentionCategoryRoute('events')).toEqual({ name: 'calendar' })
    expect(attentionCategoryRoute('grades')).toEqual({ name: 'calendar' })
    expect(attentionCategoryRoute('tenure')).toBe('/awards')
    expect(attentionCategoryRoute('contracts')).toBe('/contracts')
  })
})
