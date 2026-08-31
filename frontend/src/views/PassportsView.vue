<script setup lang="ts">
import DataTable from '@/components/DataTable.vue'
import PageState from '@/components/PageState.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/api/client'
import { useServerTable } from '@/composables/useServerTable'
import type { ColumnDef } from '@/composables/useDataTable'
import type { Paginated, PassportRow, TableQueryState } from '@/types'
import { formatShortDate } from '@/utils/dates'
import { getPassportStatusMeta } from '@/utils/statuses'

const table = useServerTable<PassportRow>({
  tableId: 'passports',
  fetcher: (params) => api.passports(params) as Promise<Paginated<PassportRow>>,
  defaultSort: { key: 'valid_until', direction: 'asc' },
})

const columns: ColumnDef<PassportRow>[] = [
  { key: 'full_name', label: 'ФИО' },
  {
    key: 'valid_until',
    label: 'Действителен до',
    getValue: (row) => row.valid_until,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'days_left',
    label: 'Осталось дней',
    getValue: (row) => row.days_left,
    format: (value) => (value == null ? '—' : String(value)),
  },
  {
    key: 'status',
    label: 'Статус',
    getValue: (row) => row.status,
    format: (value) => getPassportStatusMeta(value as string | null).label,
  },
]

function onQueryUpdate(patch: Partial<TableQueryState>) {
  table.setQuery(patch)
}
</script>

<template>
  <section class="card page">
    <header><h2>Паспорта</h2></header>
    <PageState
      :loading="table.loading.value"
      :refreshing="table.refreshing.value"
      :error="table.error.value"
      :has-data="table.rows.value.length > 0"
      @retry="table.reload()"
    >
      <DataTable
        mode="server"
        table-id="passports"
        :columns="columns"
        :rows="table.rows.value"
        row-key="person_uuid"
        :loading="table.loading.value"
        :total="table.total.value"
        :page="table.query.value.page"
        :per-page="table.query.value.per_page"
        :sort-key="table.query.value.sort"
        :sort-dir="table.query.value.direction"
        :search="table.query.value.q"
        :column-filters="table.query.value.columnFilters"
        search-placeholder="Поиск по паспортам..."
        @update:query="onQueryUpdate"
      >
        <template #cell-status="{ row }">
          <StatusBadge
            :label="getPassportStatusMeta(row.status).label"
            :variant="getPassportStatusMeta(row.status).variant"
          />
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
