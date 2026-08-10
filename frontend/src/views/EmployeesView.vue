<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import DataTable from '@/components/DataTable.vue'
import PageState from '@/components/PageState.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/api/client'
import { useServerTable } from '@/composables/useServerTable'
import type { ColumnDef } from '@/composables/useDataTable'
import type { Employee, Paginated, TableQueryState } from '@/types'
import { formatShortDate } from '@/utils/dates'
import { getPassportStatusMeta } from '@/utils/statuses'

const route = useRoute()

const table = useServerTable<Employee>({
  tableId: 'employees',
  fetcher: (params) => api.employees(params) as Promise<Paginated<Employee>>,
  defaultSort: { key: 'hire_date', direction: 'desc' },
})

const initialSearch = computed(() =>
  typeof route.query.q === 'string' ? route.query.q : '',
)

if (initialSearch.value) {
  table.setSearch(initialSearch.value)
}

const columns: ColumnDef<Employee>[] = [
  {
    key: 'index',
    label: '№',
    sortable: false,
    filterable: false,
  },
  { key: 'full_name', label: 'ФИО' },
  { key: 'title', label: 'Должность' },
  {
    key: 'position_grade',
    label: 'Грейд по должности',
    getValue: (row) => row.position_grade?.name ?? '—',
  },
  {
    key: 'actual_grade',
    label: 'Фактический грейд',
    getValue: (row) => row.actual_grade?.name ?? '—',
  },
  {
    key: 'has_university',
    label: 'ВУЗ',
    getValue: (row) => (row.has_university ? 'Да' : 'Нет'),
  },
  {
    key: 'contract_end',
    label: 'Окончание договора',
    getValue: (row) => row.contract_end,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'grade_date',
    label: 'Дата грейда',
    getValue: (row) => row.grade_date,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'hire_date',
    label: 'Начало работы',
    getValue: (row) => row.hire_date,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'tenure_years',
    label: 'Стаж',
    getValue: (row) => row.tenure_years,
    format: (value) => `${value} лет`,
  },
  {
    key: 'passport',
    label: 'Паспорт',
    getValue: (row) => row.passport_until,
    format: (value) => formatShortDate(value as string | null),
  },
]

function onQueryUpdate(patch: Partial<TableQueryState>) {
  table.setQuery(patch)
}
</script>

<template>
  <section class="card page">
    <header>
      <h2>Общая таблица сотрудников</h2>
    </header>

    <PageState
      :error="table.error.value"
      @retry="table.reload()"
    >
      <DataTable
        mode="server"
        table-id="employees"
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
        search-placeholder="Поиск по сотрудникам..."
        @update:query="onQueryUpdate"
      >
        <template #cell-index="{ row }">
          {{
            (table.query.value.page - 1) * table.query.value.per_page +
            table.rows.value.indexOf(row) +
            1
          }}
        </template>
        <template #cell-passport="{ row }">
          <StatusBadge
            :label="formatShortDate(row.passport_until)"
            :variant="getPassportStatusMeta(row.passport_status).variant"
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
