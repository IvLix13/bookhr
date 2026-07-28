<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/api/client'
import type { ColumnDef } from '@/composables/useDataTable'
import type { Employee } from '@/types'
import { formatShortDate } from '@/utils/dates'
import { getPassportStatusMeta } from '@/utils/statuses'

const employees = ref<Employee[]>([])
const loading = ref(true)

const columns: ColumnDef<Employee>[] = [
  {
    key: 'index',
    label: '№',
    sortable: false,
    filterable: false,
    getValue: (row) => employees.value.indexOf(row) + 1,
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
    sortValue: (row) => row.contract_end,
  },
  {
    key: 'grade_date',
    label: 'Дата грейда',
    getValue: (row) => row.grade_date,
    format: (value) => formatShortDate(value as string | null),
    sortValue: (row) => row.grade_date,
  },
  {
    key: 'hire_date',
    label: 'Начало работы',
    getValue: (row) => row.hire_date,
    format: (value) => formatShortDate(value as string | null),
    sortValue: (row) => row.hire_date,
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
    sortValue: (row) => row.passport_until,
  },
]

onMounted(async () => {
  employees.value = (await api.fetchAllEmployees()) as Employee[]
  loading.value = false
})
</script>

<template>
  <section class="card page">
    <header>
      <h2>Общая таблица сотрудников</h2>
    </header>
    <DataTable
      :columns="columns"
      :rows="employees"
      row-key="id"
      :loading="loading"
      search-placeholder="Поиск по сотрудникам..."
    >
      <template #cell-index="{ row }">
        {{ employees.indexOf(row) + 1 }}
      </template>
      <template #cell-passport="{ row }">
        <StatusBadge
          :label="formatShortDate(row.passport_until)"
          :variant="getPassportStatusMeta(row.passport_status).variant"
        />
      </template>
    </DataTable>
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
}
</style>
