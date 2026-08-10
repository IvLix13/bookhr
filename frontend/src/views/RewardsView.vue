<script setup lang="ts">
import DataTable from '@/components/DataTable.vue'
import PageState from '@/components/PageState.vue'
import { api } from '@/api/client'
import { useServerTable } from '@/composables/useServerTable'
import type { ColumnDef } from '@/composables/useDataTable'
import type { Paginated, RewardRow, TableQueryState } from '@/types'
import { formatShortDate } from '@/utils/dates'
import { MODULE_LABELS } from '@/utils/labels'

const table = useServerTable<RewardRow>({
  tableId: 'rewards',
  fetcher: (params) => api.rewards(params) as Promise<Paginated<RewardRow>>,
  defaultSort: { key: 'milestone_date', direction: 'desc' },
})

const columns: ColumnDef<RewardRow>[] = [
  { key: 'full_name', label: 'ФИО' },
  {
    key: 'milestone_years',
    label: 'Стаж',
    getValue: (row) => row.milestone_years,
    format: (value) => `${value} лет`,
  },
  {
    key: 'milestone_date',
    label: 'Дата награды',
    getValue: (row) => row.milestone_date,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'is_received',
    label: 'Статус',
    getValue: (row) => row.is_received,
    format: (value) => (value ? 'Получено' : 'Ожидает'),
  },
  {
    key: 'received_date',
    label: 'Дата получения',
    getValue: (row) => row.received_date,
    format: (value) => formatShortDate(value as string | null),
  },
]

function onQueryUpdate(patch: Partial<TableQueryState>) {
  table.setQuery(patch)
}
</script>

<template>
  <section class="card page">
    <header><h2>{{ MODULE_LABELS.rewards }}</h2></header>
    <PageState
      :error="table.error.value"
      @retry="table.reload()"
    >
      <DataTable
        mode="server"
        table-id="rewards"
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
        search-placeholder="Поиск по поощрениям..."
        @update:query="onQueryUpdate"
      />
    </PageState>
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
}
</style>
