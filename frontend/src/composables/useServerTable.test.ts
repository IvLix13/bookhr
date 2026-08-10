import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { useServerTable } from '@/composables/useServerTable'
import type { Paginated } from '@/types'

interface Row {
  id: number
  name: string
}

function paginated(items: Row[], page = 1, perPage = 25): Paginated<Row> {
  return {
    items,
    page,
    per_page: perPage,
    total: items.length,
    pages: Math.max(1, Math.ceil(items.length / perPage)),
  }
}

function echoFetcher() {
  return vi.fn(async (params: Record<string, unknown>) =>
    paginated([], Number(params.page ?? 1), Number(params.per_page ?? 25)),
  )
}

describe('useServerTable', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('loads rows via fetcher with buildQuery params', async () => {
    const fetcher = vi.fn(async () => paginated([{ id: 1, name: 'Alice' }]))
    const table = useServerTable<Row>({
      tableId: 'employees',
      fetcher,
    })

    await vi.runAllTimersAsync()
    await nextTick()

    expect(fetcher).toHaveBeenCalled()
    expect(table.rows.value).toEqual([{ id: 1, name: 'Alice' }])
    expect(table.total.value).toBe(1)
  })

  it('debounces search query before fetching', async () => {
    const fetcher = vi.fn(async (_params: Record<string, unknown>) => paginated([]))
    const table = useServerTable<Row>({
      tableId: 'employees-search',
      fetcher,
      debounceMs: 300,
    })

    await vi.runAllTimersAsync()
    fetcher.mockClear()

    table.setSearch('alice')
    expect(fetcher).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(300)
    await nextTick()

    expect(fetcher).toHaveBeenCalled()
    const lastCall = fetcher.mock.calls.at(-1)?.[0] as Record<string, unknown> | undefined
    expect(lastCall).toMatchObject({ q: 'alice', page: 1 })
  })

  it('persists query state to localStorage with schema version', async () => {
    const fetcher = vi.fn(async (_params: Record<string, unknown>) => paginated([]))
    const table = useServerTable<Row>({
      tableId: 'employees-persist',
      schemaVersion: 2,
      fetcher,
    })

    await vi.runAllTimersAsync()
    table.setPerPage(50)
    table.setQuery({ sort: 'name', direction: 'desc' })
    await nextTick()

    const raw = localStorage.getItem('bookuchet:table:employees-persist:v2')
    expect(raw).toBeTruthy()
    const parsed = JSON.parse(raw ?? '{}') as Record<string, unknown>
    expect(parsed.per_page).toBe(50)
    expect(parsed.sort).toBe('name')
    expect(parsed.direction).toBe('desc')
  })

  it('restores persisted state on init', async () => {
    localStorage.setItem(
      'bookuchet:table:employees-restore:v1',
      JSON.stringify({
        page: 2,
        per_page: 10,
        q: '',
        sort: 'name',
        direction: 'asc',
        columnFilters: { title: 'dev' },
      }),
    )

    const fetcher = echoFetcher()
    const table = useServerTable<Row>({
      tableId: 'employees-restore',
      fetcher,
    })

    expect(table.query.value.page).toBe(2)
    expect(table.query.value.per_page).toBe(10)
    expect(table.query.value.columnFilters).toEqual({ title: 'dev' })

    await vi.runAllTimersAsync()
    const lastCall = fetcher.mock.calls.at(-1)?.[0] as Record<string, unknown> | undefined
    expect(lastCall).toMatchObject({
      page: 2,
      per_page: 10,
      title: 'dev',
      sort: 'name',
      direction: 'asc',
    })
  })

  it('buildQueryString includes current request params', () => {
    const fetcher = vi.fn(async (_params: Record<string, unknown>) => paginated([]))
    const table = useServerTable<Row>({
      tableId: 'employees-query-string',
      fetcher,
    })

    table.setQuery({ page: 3, sort: 'name', direction: 'desc' })

    expect(table.requestParams.value).toMatchObject({
      page: 3,
      sort: 'name',
      direction: 'desc',
    })
    expect(table.buildQueryString()).toContain('page=3')
    expect(table.buildQueryString()).toContain('sort=name')
    expect(table.buildQueryString()).toContain('direction=desc')
  })
})
