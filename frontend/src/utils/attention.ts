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

export interface AttentionRouteOptions {
  /** When false, tenure items must not link to the awards section (viewer). */
  canEdit?: boolean
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

function isTenureAwardsRoute(item: BackendAttentionItem): boolean {
  return item.category === 'tenure' || item.route === '/awards'
}

export function resolveAttentionRoute(
  item: BackendAttentionItem,
  options?: AttentionRouteOptions,
): RouteLocationRaw {
  const eventId = attentionEventId(item)
  if (eventId != null) {
    return eventDetailLocation(eventId)
  }
  if (options?.canEdit === false && isTenureAwardsRoute(item)) {
    return { name: 'calendar' }
  }
  return item.route ?? `/${item.category}`
}

export function attentionCategoryRoute(
  category: string,
  options?: AttentionRouteOptions,
): RouteLocationRaw {
  switch (category) {
    case 'events':
    case 'grades':
      return { name: 'calendar' }
    case 'contracts':
      return '/contracts'
    case 'passports':
      return '/passports'
    case 'tenure':
      return options?.canEdit === false ? { name: 'calendar' } : '/awards'
    default:
      return { name: 'calendar' }
  }
}
