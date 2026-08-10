<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import { api } from '@/api/client'
import type { ColumnDef } from '@/composables/useDataTable'
import type { GradeRow } from '@/types'
import { formatShortDate } from '@/utils/dates'

const rows = ref<GradeRow[]>([])
const loading = ref(true)

const columns: ColumnDef<GradeRow>[] = [
  { key: 'full_name', label: 'ФИО' },
  {
    key: 'grade',
    label: 'Текущий грейдов',
    getValue: (row) => row.grade?.name ?? '—',
  },
  {
    key: 'grade_date',
    label: 'Дата выдачи',
    getValue: (row) => row.grade_date,
    format: (value) => formatShortDate(value as string | null),
    sortValue: (row) => row.grade_date,
  },
  {
    key: 'next_grade',
    label: 'Следующий грейдов',
    getValue: (row) => row.next_grade?.name ?? '—',
  },
  {
    key: 'eligible_date',
    label: 'Дата доступности',
    getValue: (row) => row.eligible_date,
    format: (value) => formatShortDate(value as string | null),
    sortValue: (row) => row.eligible_date,
  },
  {
    key: 'days_left',
    label: 'Осталось дней',
    getValue: (row) => row.days_left,
    format: (value) => (value == null ? '—' : String(value)),
  },
]

onMounted(async () => {
  rows.value = (await api.grades()) as GradeRow[]
  loading.value = false
})
</script>

<template>
  <section class="card page">
    <header class="page-header">
      <h2>грейды</h2>
      <RouterLink :to="{ name: 'grade-catalog' }" class="btn secondary">Справочник</RouterLink>
    </header>
    <DataTable
      :columns="columns"
      :rows="rows"
      :row-key="(row) => row.employment_id"
      :loading="loading"
      search-placeholder="Поиск по грейдым..."
    />
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
}
</style>
