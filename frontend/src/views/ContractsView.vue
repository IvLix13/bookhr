<script setup lang="ts">
import { RouterLink } from 'vue-router'
import DataTable from '@/components/DataTable.vue'
import PageState from '@/components/PageState.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/api/client'
import { useServerTable } from '@/composables/useServerTable'
import type { ColumnDef } from '@/composables/useDataTable'
import type { ContractRow, Paginated, TableQueryState } from '@/types'
import { formatLocalDate, formatShortDate } from '@/utils/dates'
import { MODULE_LABELS } from '@/utils/labels'
import { getContractReportDisplayMeta } from '@/utils/statuses'

const table = useServerTable<ContractRow>({
  tableId: 'contracts',
  fetcher: (params) => api.contracts(params) as Promise<Paginated<ContractRow>>,
  defaultSort: { key: 'end_date', direction: 'asc' },
})

const todayIso = formatLocalDate(new Date())

const columns: ColumnDef<ContractRow>[] = [
  { key: 'full_name', label: 'ФИО' },
  {
    key: 'end_date',
    label: 'Окончание',
    getValue: (row) => row.end_date,
    format: (value) => formatShortDate(value as string | null),
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
    format: (value) => formatShortDate(value as string | null),
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
        row.renewal_report_event?.effective_status,
      ).label,
  },
  {
    key: 'report_link',
    label: '',
    sortable: false,
    filterable: false,
  },
]

function onQueryUpdate(patch: Partial<TableQueryState>) {
  table.setQuery(patch)
}
</script>

<template>
  <section class="card page">
    <header><h2>{{ MODULE_LABELS.contracts }}</h2></header>
    <PageState
      :error="table.error.value"
      @retry="table.reload()"
    >
      <DataTable
        mode="server"
        table-id="contracts"
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
        search-placeholder="Поиск по договорам..."
        @update:query="onQueryUpdate"
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
                row.renewal_report_event.effective_status,
              ).label
            "
            :variant="
              getContractReportDisplayMeta(
                row.renewal_report_event.event_date,
                row.renewal_report_event.status,
                todayIso,
                row.renewal_report_event.effective_status,
              ).variant
            "
          />
          <span v-else>—</span>
        </template>
        <template #cell-report_link="{ row }">
          <RouterLink
            v-if="row.renewal_report_event"
            :to="{ name: 'events', query: { event: String(row.renewal_report_event.id) } }"
            class="btn secondary"
          >
            Мероприятие
          </RouterLink>
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
