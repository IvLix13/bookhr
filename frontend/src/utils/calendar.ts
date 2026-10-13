import { api } from '@/api/client'
import type { EventItem, Paginated } from '@/types'
import { isShownOnCalendar } from '@/utils/statuses'

/** Load the whole date range so contract expirations are not lost after page one. */
export async function loadCalendarEvents(from: string, to: string): Promise<EventItem[]> {
  const items: EventItem[] = []
  let page = 1
  let pages = 1
  do {
    const data = (await api.events({ from, to, per_page: 200, page })) as Paginated<EventItem>
    items.push(...data.items.filter((event) => isShownOnCalendar(event.status)))
    pages = data.pages
    page += 1
  } while (page <= pages)
  return items
}
