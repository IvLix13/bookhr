import { computed, ref, type Ref } from 'vue'
import { parseIsoDate } from '@/utils/dates'

export type SortDirection = 'asc' | 'desc'

export interface ColumnDef<T> {
  key: string
  label: string
  sortable?: boolean
  filterable?: boolean
  getValue?: (row: T) => unknown
  format?: (value: unknown, row: T) => string
  sortValue?: (row: T) => string | number | null
}

function defaultGetValue<T>(row: T, key: string): unknown {
  return (row as Record<string, unknown>)[key]
}

function compareValues(left: unknown, right: unknown): number {
  if (left == null && right == null) return 0
  if (left == null) return 1
  if (right == null) return -1

  if (typeof left === 'number' && typeof right === 'number') {
    return left - right
  }

  const leftIso = typeof left === 'string' ? parseIsoDate(left) : null
  const rightIso = typeof right === 'string' ? parseIsoDate(right) : null
  if (leftIso != null && rightIso != null) {
    return leftIso - rightIso
  }

  return String(left).localeCompare(String(right), 'ru', { sensitivity: 'base' })
}

export function useDataTable<T>(rows: Ref<T[]>, columns: ColumnDef<T>[]) {
  const search = ref('')
  const sortKey = ref<string | null>(null)
  const sortDir = ref<SortDirection>('asc')
  const columnFilters = ref<Record<string, string>>({})

  const columnByKey = computed(() => {
    const map = new Map<string, ColumnDef<T>>()
    for (const column of columns) {
      map.set(column.key, column)
    }
    return map
  })

  function getCellValue(row: T, column: ColumnDef<T>): unknown {
    if (column.getValue) return column.getValue(row)
    return defaultGetValue(row, column.key)
  }

  function getDisplayValue(row: T, column: ColumnDef<T>): string {
    const value = getCellValue(row, column)
    if (column.format) return column.format(value, row)
    if (value == null || value === '') return '—'
    return String(value)
  }

  function getSortValue(row: T, column: ColumnDef<T>): unknown {
    if (column.sortValue) return column.sortValue(row)
    return getCellValue(row, column)
  }

  const filteredRows = computed(() => {
    const query = search.value.trim().toLowerCase()
    let result = rows.value.filter((row) => {
      if (query) {
        const haystack = columns
          .map((column) => getDisplayValue(row, column))
          .join(' ')
          .toLowerCase()
        if (!haystack.includes(query)) return false
      }

      for (const column of columns) {
        if (column.filterable === false) continue
        const filter = columnFilters.value[column.key]?.trim().toLowerCase()
        if (!filter) continue
        const display = getDisplayValue(row, column).toLowerCase()
        if (!display.includes(filter)) return false
      }

      return true
    })

    if (sortKey.value) {
      const column = columnByKey.value.get(sortKey.value)
      if (column) {
        const direction = sortDir.value === 'asc' ? 1 : -1
        result = [...result].sort((left, right) => {
          const cmp = compareValues(getSortValue(left, column), getSortValue(right, column))
          return cmp * direction
        })
      }
    }

    return result
  })

  function toggleSort(key: string) {
    if (sortKey.value === key) {
      sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
      return
    }
    sortKey.value = key
    sortDir.value = 'asc'
  }

  function setColumnFilter(key: string, value: string) {
    columnFilters.value = { ...columnFilters.value, [key]: value }
  }

  function resetFilters() {
    search.value = ''
    columnFilters.value = {}
    sortKey.value = null
    sortDir.value = 'asc'
  }

  const hasActiveFilters = computed(() => {
    if (search.value.trim()) return true
    return Object.values(columnFilters.value).some((value) => value.trim())
  })

  return {
    search,
    sortKey,
    sortDir,
    columnFilters,
    filteredRows,
    toggleSort,
    setColumnFilter,
    resetFilters,
    hasActiveFilters,
    getDisplayValue,
  }
}
