import { ref } from 'vue'
import { describe, expect, it } from 'vitest'
import { useDataTable, type ColumnDef } from '@/composables/useDataTable'

interface Row {
  name: string
  date: string
  amount: number
}

const columns: ColumnDef<Row>[] = [
  { key: 'name', label: 'Name' },
  {
    key: 'date',
    label: 'Date',
    getValue: (row) => row.date,
    sortValue: (row) => row.date,
  },
  { key: 'amount', label: 'Amount' },
]

describe('useDataTable', () => {
  it('filters rows by global search', () => {
    const rows = ref<Row[]>([
      { name: 'Alice', date: '2026-01-01', amount: 10 },
      { name: 'Bob', date: '2026-02-01', amount: 20 },
    ])
    const table = useDataTable(rows, columns)
    table.search.value = 'bob'
    expect(table.filteredRows.value).toHaveLength(1)
    expect(table.filteredRows.value[0]?.name).toBe('Bob')
  })

  it('sorts rows by selected column', () => {
    const rows = ref<Row[]>([
      { name: 'Alice', date: '2026-03-01', amount: 10 },
      { name: 'Bob', date: '2026-01-01', amount: 20 },
    ])
    const table = useDataTable(rows, columns)
    table.toggleSort('date')
    expect(table.filteredRows.value.map((row) => row.name)).toEqual(['Bob', 'Alice'])
  })

  it('filters rows by column filter', () => {
    const rows = ref<Row[]>([
      { name: 'Alice', date: '2026-01-01', amount: 10 },
      { name: 'Bob', date: '2026-02-01', amount: 20 },
    ])
    const table = useDataTable(rows, columns)
    table.setColumnFilter('name', 'ali')
    expect(table.filteredRows.value).toHaveLength(1)
    expect(table.filteredRows.value[0]?.name).toBe('Alice')
  })

  it('resets search, sort and filters', () => {
    const rows = ref<Row[]>([{ name: 'Alice', date: '2026-01-01', amount: 10 }])
    const table = useDataTable(rows, columns)
    table.search.value = 'missing'
    table.toggleSort('amount')
    table.setColumnFilter('name', 'x')
    table.resetFilters()
    expect(table.search.value).toBe('')
    expect(table.sortKey.value).toBeNull()
    expect(table.filteredRows.value).toHaveLength(1)
  })

  it('paginates filtered rows when enabled', () => {
    const rows = ref<Row[]>([
      { name: 'Alice', date: '2026-01-01', amount: 10 },
      { name: 'Bob', date: '2026-02-01', amount: 20 },
      { name: 'Carol', date: '2026-03-01', amount: 30 },
    ])
    const table = useDataTable(rows, columns, { paginate: true, perPage: 2 })
    expect(table.paginatedRows.value).toHaveLength(2)
    table.setPage(2)
    expect(table.paginatedRows.value).toHaveLength(1)
    expect(table.totalPages.value).toBe(2)
  })
})
