<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import { api } from '@/api/client'
import type { ColumnDef } from '@/composables/useDataTable'
import type { ContractRow } from '@/types'
import { formatShortDate } from '@/utils/dates'

const rows = ref<ContractRow[]>([])
const loading = ref(true)

const columns: ColumnDef<ContractRow>[] = [
  { key: 'full_name', label: 'ФИО' },
  {
    key: 'end_date',
    label: 'Окончание',
    getValue: (row) => row.end_date,
    format: (value) => formatShortDate(value as string | null),
    sortValue: (row) => row.end_date,
  },
  {
    key: 'days_left',
    label: 'Осталось дней',
    getValue: (row) => row.days_left,
  },
]

onMounted(async () => {
  rows.value = (await api.contracts()) as ContractRow[]
  loading.value = false
})
</script>

<template>
  <section class="card page">
    <header><h2>Контракты</h2></header>
    <DataTable
      :columns="columns"
      :rows="rows"
      row-key="id"
      :loading="loading"
      search-placeholder="Поиск по контрактам..."
    >
      <template #cell-days_left="{ row }">
        <span class="badge" :class="row.days_left <= 120 ? 'warning' : ''">{{ row.days_left }}</span>
      </template>
    </DataTable>
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
}
</style>
