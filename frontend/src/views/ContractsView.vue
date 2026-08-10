<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/api/client'
import type { ColumnDef } from '@/composables/useDataTable'
import type { ContractRow } from '@/types'
import { formatLocalDate, formatNumericDate } from '@/utils/dates'
import { getContractReportDisplayMeta } from '@/utils/statuses'

const rows = ref<ContractRow[]>([])
const loading = ref(true)
const todayIso = formatLocalDate(new Date())

const columns: ColumnDef<ContractRow>[] = [
  { key: 'full_name', label: 'ФИО' },
  {
    key: 'end_date',
    label: 'Окончание',
    getValue: (row) => row.end_date,
    format: (value) => formatNumericDate(value as string | null),
    sortValue: (row) => row.end_date,
  },
  {
    key: 'days_left',
    label: 'Осталось дней',
    getValue: (row) => row.days_left,
  },
  {
    key: 'report_date',
    label: 'Дата рапорта',
    getValue: (row) => row.renewal_report_event?.event_date ?? null,
    format: (value) => formatNumericDate(value as string | null),
    sortValue: (row) => row.renewal_report_event?.event_date ?? null,
  },
  {
    key: 'report_status',
    label: 'Статус рапорта',
    getValue: (row) => row.renewal_report_event?.status ?? null,
    format: (value, row) =>
      getContractReportDisplayMeta(
        row.renewal_report_event?.event_date ?? null,
        value as string | null,
        todayIso,
      ).label,
    sortValue: (row) => row.renewal_report_event?.status ?? null,
  },
  {
    key: 'report_link',
    label: '',
    sortable: false,
    filterable: false,
  },
]

onMounted(async () => {
  rows.value = (await api.contracts()) as ContractRow[]
  loading.value = false
})
</script>

<template>
  <section class="card page">
    <header><h2>Договоры</h2></header>
    <DataTable
      :columns="columns"
      :rows="rows"
      row-key="id"
      :loading="loading"
      search-placeholder="Поиск по Договорам..."
    >
      <template #cell-days_left="{ row }">
        <span class="badge" :class="row.days_left <= 120 ? 'warning' : ''">{{ row.days_left }}</span>
      </template>
      <template #cell-report_status="{ row }">
        <StatusBadge
          v-if="row.renewal_report_event"
          :label="
            getContractReportDisplayMeta(
              row.renewal_report_event.event_date,
              row.renewal_report_event.status,
              todayIso,
            ).label
          "
          :variant="
            getContractReportDisplayMeta(
              row.renewal_report_event.event_date,
              row.renewal_report_event.status,
              todayIso,
            ).variant
          "
        />
        <span v-else>—</span>
      </template>
      <template #cell-report_link="{ row }">
        <RouterLink
          v-if="row.renewal_report_event"
          :to="{ name: 'events', query: { highlight: String(row.renewal_report_event.id) } }"
          class="btn secondary"
        >
          Мероприятие
        </RouterLink>
      </template>
    </DataTable>
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
}
</style>
