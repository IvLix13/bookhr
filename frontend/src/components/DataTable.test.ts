import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import DataTable from '@/components/DataTable.vue'
import type { ColumnDef } from '@/composables/useDataTable'

interface Row {
  id: number
  name: string
  status?: string
}

const columns: ColumnDef<Row>[] = [
  { key: 'name', label: 'Имя' },
  {
    key: 'status',
    label: 'Статус',
    cellClass: (row) => (row.status === 'ok' ? 'cell-ok' : undefined),
  },
]

describe('DataTable row-click', () => {
  it('emits row-click when rowClickable is enabled', async () => {
    const wrapper = mount(DataTable<Row>, {
      props: {
        columns,
        rows: [{ id: 1, name: 'Alpha' }],
        rowKey: 'id',
        rowClickable: true,
      },
    })

    await wrapper.get('.data-table-row').trigger('click')
    expect(wrapper.emitted('row-click')?.[0]?.[0]).toEqual({ id: 1, name: 'Alpha' })
  })

  it('does not emit row-click when rowClickable is disabled', async () => {
    const wrapper = mount(DataTable<Row>, {
      props: {
        columns,
        rows: [{ id: 1, name: 'Alpha' }],
        rowKey: 'id',
      },
    })

    await wrapper.get('.data-table-row').trigger('click')
    expect(wrapper.emitted('row-click')).toBeUndefined()
  })

  it('applies cellClass to table cells', () => {
    const wrapper = mount(DataTable<Row>, {
      props: {
        columns,
        rows: [{ id: 1, name: 'Alpha', status: 'ok' }],
        rowKey: 'id',
      },
    })

    expect(wrapper.find('.cell-ok').exists()).toBe(true)
  })

  it('resets server filters to provided default sort', async () => {
    const wrapper = mount(DataTable<Row>, {
      props: {
        mode: 'server',
        columns,
        rows: [{ id: 1, name: 'Alpha' }],
        rowKey: 'id',
        search: 'test',
        columnFilters: { name: 'a' },
        defaultSortKey: 'nearest_date',
        defaultSortDir: 'asc',
      },
    })

    await wrapper.get('.data-table-reset').trigger('click')
    expect(wrapper.emitted('update:query')?.[0]?.[0]).toMatchObject({
      q: '',
      sort: 'nearest_date',
      direction: 'asc',
      columnFilters: {},
      page: 1,
    })
  })
})
