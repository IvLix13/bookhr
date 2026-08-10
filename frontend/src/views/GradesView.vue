<script setup lang="ts">
import { RouterLink } from 'vue-router'
import DataTable from '@/components/DataTable.vue'
import PageState from '@/components/PageState.vue'
import { api } from '@/api/client'
import { useServerTable } from '@/composables/useServerTable'
import type { ColumnDef } from '@/composables/useDataTable'
import type { GradeRow, Paginated, TableQueryState } from '@/types'
import { formatShortDate } from '@/utils/dates'
import { MODULE_LABELS } from '@/utils/labels'

const table = useServerTable<GradeRow>({
  tableId: 'grades',
  fetcher: (params) => api.grades(params) as Promise<Paginated<GradeRow>>,
  defaultSort: { key: 'eligible_date', direction: 'asc' },
})

const columns: ColumnDef<GradeRow>[] = [
  { key: 'full_name', label: 'ФИО' },
  {
    key: 'grade',
    label: 'Текущий грейд',
    getValue: (row) => row.grade?.name ?? '—',
  },
  {
    key: 'grade_date',
    label: 'Дата выдачи',
    getValue: (row) => row.grade_date,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'next_grade',
    label: 'Следующий грейд',
    getValue: (row) => row.next_grade?.name ?? '—',
  },
  {
    key: 'eligible_date',
    label: 'Дата доступности',
    getValue: (row) => row.eligible_date,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'days_left',
    label: 'Осталось дней',
    getValue: (row) => row.days_left,
    format: (value) => (value == null ? '—' : String(value)),
  },
]

function onQueryUpdate(patch: Partial<TableQueryState>) {
  table.setQuery(patch)
}
</script>

<template>
  <section class="card page">
    <header class="page-header">
      <h2>Грейды</h2>
      <RouterLink class="btn secondary" to="/grade-catalog">
        {{ MODULE_LABELS.gradeCatalog }}
      </RouterLink>
    </header>
    <PageState
      :error="table.error.value"
      @retry="table.reload()"
    >
      <DataTable
        mode="server"
        table-id="grades"
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
        search-placeholder="Поиск по грейдам..."
        @update:query="onQueryUpdate"
      />
    </PageState>
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.page-header h2 {
  margin: 0;
}
</style>
