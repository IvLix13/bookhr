<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import { api } from '@/api/client'
import type { ColumnDef } from '@/composables/useDataTable'
import type { TenureRow } from '@/types'

const rows = ref<TenureRow[]>([])
const loading = ref(true)

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
    getValue: (row) => (row.awards['10']?.is_received ? 'Получено' : '—'),
  },
  {
    key: 'award_15',
    label: '15 лет',
    getValue: (row) => (row.awards['15']?.is_received ? 'Получено' : '—'),
  },
  {
    key: 'award_20',
    label: '20 лет',
    getValue: (row) => (row.awards['20']?.is_received ? 'Получено' : '—'),
  },
]

onMounted(async () => {
  rows.value = (await api.tenure()) as TenureRow[]
  loading.value = false
})
</script>

<template>
  <section class="card page">
    <header><h2>Поощрения</h2></header>
    <DataTable
      :columns="columns"
      :rows="rows"
      :row-key="(row) => row.employment_id"
      :loading="loading"
      search-placeholder="Поиск по поощрениям..."
    />
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
}
</style>
