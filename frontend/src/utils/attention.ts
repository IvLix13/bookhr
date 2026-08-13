import type { RouteLocationRaw } from 'vue-router'

export interface BackendAttentionItem {
  category: string
  id: number | string
  title: string
  subtitle?: string | null
  due_date?: string | null
  severity: 'info' | 'warning' | 'danger'
  route?: string | null
}

const CALENDAR_STAY_CATEGORIES = new Set(['events', 'grades'])

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
  const fromRoute = eventIdFromAttentionRoute(item.route)
  if (fromRoute != null) return fromRoute
  const route = item.route ?? ''
  const looksLikeEvent =
    item.category === 'events' || route === '/events' || route.startsWith('/events?')
  if (!looksLikeEvent) return null
  const parsed = Number(item.id)
  return Number.isFinite(parsed) ? parsed : null
}

export function staysOnCalendar(item: BackendAttentionItem): boolean {
  if (CALENDAR_STAY_CATEGORIES.has(item.category)) return true
  const route = item.route ?? ''
  return (
    route === '/events' ||
    route.startsWith('/events?') ||
    route.startsWith('/?event=') ||
    route === '/grades' ||
    route.startsWith('/grades?')
  )
}

export function isAttentionEvent(item: BackendAttentionItem): boolean {
  return staysOnCalendar(item)
}

export function eventDetailLocation(eventId: number | string): RouteLocationRaw {
  return { name: 'calendar', query: { event: String(eventId) } }
}

export function resolveAttentionRoute(item: BackendAttentionItem): RouteLocationRaw {
  const eventId = attentionEventId(item)
  if (eventId != null) {
    return eventDetailLocation(eventId)
  }
  if (staysOnCalendar(item)) {
    return { name: 'calendar' }
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
