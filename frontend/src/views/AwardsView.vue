<script setup lang="ts">
import DataTable from '@/components/DataTable.vue'
import PageState from '@/components/PageState.vue'
import { api } from '@/api/client'
import { useServerTable } from '@/composables/useServerTable'
import type { ColumnDef } from '@/composables/useDataTable'
import type { Paginated, TableQueryState, TenureRow } from '@/types'
import { MODULE_LABELS } from '@/utils/labels'
import { formatNumericDate } from '@/utils/dates'

const table = useServerTable<TenureRow>({
  tableId: 'awards',
  fetcher: (params) => api.tenure(params) as Promise<Paginated<TenureRow>>,
  defaultSort: { key: 'tenure_years', direction: 'desc' },
})

function awardLabel(row: TenureRow, years: '10' | '15' | '20'): string {
  const award = row.awards[years]
  if (!award) return '—'
  if (award.is_received) return 'Получено'
  if (award.milestone_date) return formatNumericDate(award.milestone_date)
  return '—'
}

const columns: ColumnDef<TenureRow>[] = [
  { key: 'full_name', label: 'ФИО' },
  {
    key: 'tenure_years',
    label: 'Стаж',
    getValue: (row) => row.tenure_years,
    format: (value) => `${value} лет`,
  },
  {
    key: 'award_10',
    label: '10 лет',
    getValue: (row) => awardLabel(row, '10'),
  },
  {
    key: 'award_15',
    label: '15 лет',
    getValue: (row) => awardLabel(row, '15'),
  },
  {
    key: 'award_20',
    label: '20 лет',
    getValue: (row) => awardLabel(row, '20'),
  },
]

function onQueryUpdate(patch: Partial<TableQueryState>) {
  table.setQuery(patch)
}
</script>

<template>
  <section class="card page">
    <header><h2>{{ MODULE_LABELS.awards }}</h2></header>
    <PageState
      :error="table.error.value"
      @retry="table.reload()"
    >
      <DataTable
        mode="server"
        table-id="awards"
        :columns="columns"
        :rows="table.rows.value"
        :row-key="(row) => row.employment_id"
        :loading="table.loading.value"
        :total="table.total.value"
        :page="table.query.value.page"
        :per-page="table.query.value.per_page"
        :sort-key="table.query.value.sort"
        :sort-dir="table.query.value.direction"
        :search="table.query.value.q"
        :column-filters="table.query.value.columnFilters"
        search-placeholder="Поиск по наградам за стаж..."
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
