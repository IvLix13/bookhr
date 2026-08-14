import type { RouteLocationRaw } from 'vue-router'

export interface BackendAttentionItem {
  category: string
  id: number | string
  title: string
  subtitle?: string | null
  due_date?: string | null
  severity: 'info' | 'warning' | 'danger'
  route?: string | null
  event_id?: number | null
}

export function attentionItemKey(item: BackendAttentionItem): string {
  return `${item.category}-${item.id}`
}

export function eventIdFromAttentionRoute(route: string | null | undefined): number | null {
  if (!route) return null
  const match = /(?:\?|&)event=(\d+)/.exec(route) ?? /^\/\?event=(\d+)/.exec(route)
  if (!match) return null
  const parsed = Number(match[1])
  return Number.isFinite(parsed) ? parsed : null
}

export function attentionEventId(item: BackendAttentionItem): number | null {
  if (item.event_id != null && Number.isFinite(item.event_id)) return item.event_id
  const fromRoute = eventIdFromAttentionRoute(item.route)
  if (fromRoute != null) return fromRoute
  const route = item.route ?? ''
  const looksLikeEvent =
    item.category === 'events' || route === '/events' || route.startsWith('/events?')
  if (!looksLikeEvent) return null
  const parsed = Number(item.id)
  return Number.isFinite(parsed) ? parsed : null
}

/** Items backed by an event are handled in a modal instead of navigating away. */
export function canOpenAttentionEvent(item: BackendAttentionItem): boolean {
  return attentionEventId(item) != null
}

export function eventDetailLocation(eventId: number | string): RouteLocationRaw {
  return { name: 'calendar', query: { event: String(eventId) } }
}

export function resolveAttentionRoute(item: BackendAttentionItem): RouteLocationRaw {
  const eventId = attentionEventId(item)
  if (eventId != null) {
    return eventDetailLocation(eventId)
  }
  return item.route ?? `/${item.category}`
}

export function attentionCategoryRoute(category: string): RouteLocationRaw {
  switch (category) {
    case 'events':
    case 'grades':
      return { name: 'calendar' }
    case 'contracts':
      return '/contracts'
    case 'passports':
      return '/passports'
    case 'tenure':
      return '/awards'
    default:
      return { name: 'calendar' }
  }
}
