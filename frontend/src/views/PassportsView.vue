<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/api/client'
import type { ColumnDef } from '@/composables/useDataTable'
import type { PassportRow } from '@/types'
import { formatShortDate } from '@/utils/dates'
import { getPassportStatusMeta } from '@/utils/statuses'

const rows = ref<PassportRow[]>([])
const loading = ref(true)

const columns: ColumnDef<PassportRow>[] = [
  { key: 'full_name', label: 'ФИО' },
  {
    key: 'valid_until',
    label: 'Действителен до',
    getValue: (row) => row.valid_until,
    format: (value) => formatShortDate(value as string | null),
    sortValue: (row) => row.valid_until,
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
    sortValue: (row) => row.status,
  },
]

onMounted(async () => {
  rows.value = (await api.passports()) as PassportRow[]
  loading.value = false
})
</script>

<template>
  <section class="card page">
    <header><h2>Паспорта</h2></header>
    <DataTable
      :columns="columns"
      :rows="rows"
      row-key="person_uuid"
      :loading="loading"
      search-placeholder="Поиск по паспортам..."
    >
      <template #cell-status="{ row }">
        <StatusBadge
          :label="getPassportStatusMeta(row.status).label"
          :variant="getPassportStatusMeta(row.status).variant"
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
