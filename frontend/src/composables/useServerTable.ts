import { computed, ref, watch, type Ref } from 'vue'
import { buildQuery, type TableQueryParams } from '@/api/client'
import { normalizeError } from '@/api/errors'
import type { Paginated, TableQueryState } from '@/types'

const DEFAULT_SCHEMA_VERSION = 1
const DEFAULT_DEBOUNCE_MS = 300
const DEFAULT_PER_PAGE = 25

function storageKey(tableId: string, schemaVersion: number): string {
  return `bookuchet:table:${tableId}:v${schemaVersion}`
}

function readPersistedState(
  tableId: string,
  schemaVersion: number,
  defaults: TableQueryState,
): TableQueryState {
  try {
    const raw = localStorage.getItem(storageKey(tableId, schemaVersion))
    if (!raw) return defaults
    const parsed = JSON.parse(raw) as Partial<TableQueryState>
    return {
      page: typeof parsed.page === 'number' && parsed.page > 0 ? parsed.page : defaults.page,
      per_page:
        typeof parsed.per_page === 'number' && parsed.per_page > 0
          ? parsed.per_page
          : defaults.per_page,
      q: typeof parsed.q === 'string' ? parsed.q : defaults.q,
      sort: typeof parsed.sort === 'string' ? parsed.sort : parsed.sort === null ? null : defaults.sort,
      direction: parsed.direction === 'desc' ? 'desc' : defaults.direction,
      columnFilters:
        parsed.columnFilters && typeof parsed.columnFilters === 'object'
          ? { ...parsed.columnFilters }
          : defaults.columnFilters,
    }
  } catch {
    return defaults
  }
}

function writePersistedState(tableId: string, schemaVersion: number, state: TableQueryState) {
  try {
    localStorage.setItem(storageKey(tableId, schemaVersion), JSON.stringify(state))
  } catch {
    // ignore storage errors
  }
}

function debounce<T extends (...args: never[]) => void>(fn: T, delayMs: number): T {
  let timer: ReturnType<typeof setTimeout> | null = null
  return ((...args: Parameters<T>) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delayMs)
  }) as T
}

export interface UseServerTableOptions<T> {
  tableId: string
  fetcher: (params: TableQueryParams) => Promise<Paginated<T>>
  schemaVersion?: number
  debounceMs?: number
  defaultPerPage?: number
  defaultSort?: { key: string; direction: 'asc' | 'desc' }
}

export function useServerTable<T>(options: UseServerTableOptions<T>) {
  const schemaVersion = options.schemaVersion ?? DEFAULT_SCHEMA_VERSION
  const debounceMs = options.debounceMs ?? DEFAULT_DEBOUNCE_MS
  const defaultPerPage = options.defaultPerPage ?? DEFAULT_PER_PAGE

  const defaults: TableQueryState = {
    page: 1,
    per_page: defaultPerPage,
    q: '',
    sort: options.defaultSort?.key ?? null,
    direction: options.defaultSort?.direction ?? 'asc',
    columnFilters: {},
  }

  const query = ref<TableQueryState>(
    readPersistedState(options.tableId, schemaVersion, defaults),
  ) as Ref<TableQueryState>
  const debouncedQ = ref(query.value.q)
  const rows = ref([] as T[]) as Ref<T[]>
  const total = ref(0)
  const pages = ref(0)
  const loading = ref(false)
  const refreshing = ref(false)
  const error = ref('')
  let requestId = 0

  const debouncedSyncQ = debounce((value: string) => {
    debouncedQ.value = value
  }, debounceMs)

  watch(
    () => query.value.q,
    (value) => {
      debouncedSyncQ(value)
    },
    { immediate: true },
  )

  watch(
    query,
    (state) => {
      writePersistedState(options.tableId, schemaVersion, state)
    },
    { deep: true },
  )

  const requestParams = computed<TableQueryParams>(() => {
    const params: TableQueryParams = {
      page: query.value.page,
      per_page: query.value.per_page,
    }
    const trimmedQ = debouncedQ.value.trim()
    if (trimmedQ) params.q = trimmedQ
    if (query.value.sort) {
      params.sort = query.value.sort
      params.direction = query.value.direction
    }
    for (const [key, value] of Object.entries(query.value.columnFilters)) {
      const trimmed = value.trim()
      if (trimmed) params[key] = trimmed
    }
    return params
  })

  async function load() {
    const currentId = ++requestId
    const hasRows = rows.value.length > 0
    loading.value = !hasRows
    refreshing.value = hasRows
    error.value = ''

    try {
      const result = await options.fetcher(requestParams.value)
      if (currentId !== requestId) return
      rows.value = result.items
      total.value = result.total
      pages.value = result.pages
      if (result.page !== query.value.page) {
        query.value = { ...query.value, page: result.page }
      }
    } catch (err) {
      if (currentId !== requestId) return
      error.value = normalizeError(err)
      if (!hasRows) rows.value = []
    } finally {
      if (currentId === requestId) {
        loading.value = false
        refreshing.value = false
      }
    }
  }

  watch(requestParams, () => {
    void load()
  }, { immediate: true })

  function setQuery(patch: Partial<TableQueryState>) {
    const next = { ...query.value, ...patch }
    if (patch.q !== undefined && patch.q !== query.value.q) {
      next.page = 1
    }
    if (patch.columnFilters !== undefined || patch.per_page !== undefined) {
      if (patch.columnFilters !== undefined && patch.page === undefined) {
        next.page = 1
      }
    }
    if (patch.sort !== undefined && patch.page === undefined && patch.sort !== query.value.sort) {
      next.page = 1
    }
    query.value = next
  }

  function setSearch(value: string) {
    setQuery({ q: value, page: 1 })
  }

  function setPage(page: number) {
    setQuery({ page: Math.max(1, page) })
  }

  function setPerPage(perPage: number) {
    setQuery({ per_page: Math.max(1, perPage), page: 1 })
  }

  function toggleSort(key: string) {
    if (query.value.sort === key) {
      setQuery({
        direction: query.value.direction === 'asc' ? 'desc' : 'asc',
        page: 1,
      })
      return
    }
    setQuery({ sort: key, direction: 'asc', page: 1 })
  }

  function setColumnFilter(key: string, value: string) {
    setQuery({
      columnFilters: { ...query.value.columnFilters, [key]: value },
      page: 1,
    })
  }

  function resetFilters() {
    setQuery({
      q: '',
      sort: options.defaultSort?.key ?? null,
      direction: options.defaultSort?.direction ?? 'asc',
      columnFilters: {},
      page: 1,
    })
  }

  const hasActiveFilters = computed(() => {
    if (query.value.q.trim()) return true
    return Object.values(query.value.columnFilters).some((value) => value.trim())
  })

  function buildQueryString(extra: TableQueryParams = {}): string {
    return buildQuery({ ...requestParams.value, ...extra })
  }

  return {
    query,
    debouncedQ,
    rows,
    total,
    pages,
    loading,
    refreshing,
    error,
    hasActiveFilters,
    requestParams,
    setQuery,
    setSearch,
    setPage,
    setPerPage,
    toggleSort,
    setColumnFilter,
    resetFilters,
    reload: load,
    buildQueryString,
  }
}
