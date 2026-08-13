import { describe, expect, it } from 'vitest'
import {
  attentionCategoryRoute,
  attentionItemKey,
  resolveAttentionRoute,
} from '@/utils/attention'

describe('attention utils', () => {
  it('builds stable item keys', () => {
    expect(attentionItemKey({ category: 'events', id: 5, title: 'x', severity: 'danger' })).toBe(
      'events-5',
    )
  })

  it('routes events with event query for detail modal', () => {
    expect(
      resolveAttentionRoute({
        category: 'events',
        id: 12,
        title: 'Test',
        severity: 'warning',
      }),
    ).toBe('/events?event=12')
  })

  it('maps category summary routes', () => {
    expect(attentionCategoryRoute('tenure')).toBe('/awards')
    expect(attentionCategoryRoute('contracts')).toBe('/contracts')
  })
})
