import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import DataTable from '@/components/DataTable.vue'
import type { ColumnDef } from '@/composables/useDataTable'

interface Row {
  id: number
  name: string
}

const columns: ColumnDef<Row>[] = [
  { key: 'name', label: 'Имя' },
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
})
