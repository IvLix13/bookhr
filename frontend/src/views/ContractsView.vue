<script setup lang="ts">
import DataTable from '@/components/DataTable.vue'
import PageState from '@/components/PageState.vue'
import { api } from '@/api/client'
import { useServerTable } from '@/composables/useServerTable'
import type { ColumnDef } from '@/composables/useDataTable'
import type { ContractRow, Paginated, TableQueryState } from '@/types'
import { formatShortDate } from '@/utils/dates'
import { MODULE_LABELS } from '@/utils/labels'

const table = useServerTable<ContractRow>({
  tableId: 'contracts',
  fetcher: (params) => api.contracts(params) as Promise<Paginated<ContractRow>>,
  defaultSort: { key: 'end_date', direction: 'asc' },
})

const columns: ColumnDef<ContractRow>[] = [
  { key: 'full_name', label: 'ФИО' },
  {
    key: 'end_date',
    label: 'Окончание',
    getValue: (row) => row.end_date,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'days_left',
    label: 'Осталось дней',
    getValue: (row) => row.days_left,
  },
]

function onQueryUpdate(patch: Partial<TableQueryState>) {
  table.setQuery(patch)
}
</script>

<template>
  <section class="card page">
    <header><h2>{{ MODULE_LABELS.contracts }}</h2></header>
    <PageState
      :error="table.error.value"
      @retry="table.reload()"
    >
      <DataTable
        mode="server"
        table-id="contracts"
        :columns="columns"
        :rows="table.rows.value"
        row-key="id"
        :loading="table.loading.value"
        :total="table.total.value"
        :page="table.query.value.page"
        :per-page="table.query.value.per_page"
        :sort-key="table.query.value.sort"
        :sort-dir="table.query.value.direction"
        :search="table.query.value.q"
        :column-filters="table.query.value.columnFilters"
        search-placeholder="Поиск по договорам..."
        @update:query="onQueryUpdate"
      >
        <template #cell-days_left="{ row }">
          <span class="badge" :class="row.days_left <= 120 ? 'warning' : ''">{{ row.days_left }}</span>
        </template>
      </DataTable>
    </PageState>
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
}
</style>
