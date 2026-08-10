export interface BackendAttentionItem {
  category: string
  id: number | string
  title: string
  subtitle?: string | null
  due_date?: string | null
  severity: 'info' | 'warning' | 'danger'
  route?: string | null
}

export function attentionItemKey(item: BackendAttentionItem): string {
  return `${item.category}-${item.id}`
}

export function resolveAttentionRoute(item: BackendAttentionItem): string {
  if (item.category === 'events') {
    return `/events?highlight=${item.id}`
  }
  return item.route ?? `/${item.category}`
}

export function attentionCategoryRoute(category: string): string {
  switch (category) {
    case 'events':
      return '/events?status=overdue'
    case 'contracts':
      return '/contracts'
    case 'passports':
      return '/passports'
    case 'grades':
      return '/grades'
    case 'tenure':
      return '/awards'
    default:
      return '/'
  }
}
