<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import DataTable from '@/components/DataTable.vue'
import PageState from '@/components/PageState.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/api/client'
import { useServerTable } from '@/composables/useServerTable'
import { useToast } from '@/composables/useToast'
import type { ColumnDef } from '@/composables/useDataTable'
import type { EventItem, Paginated, TableQueryState } from '@/types'
import { formatShortDate } from '@/utils/dates'
import { labelEventSource, labelEventType } from '@/utils/labels'
import { getEventStatusMeta } from '@/utils/statuses'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const toast = useToast()

const table = useServerTable<EventItem>({
  tableId: 'events',
  fetcher: (params) => api.events(params) as Promise<Paginated<EventItem>>,
  defaultSort: { key: 'event_date', direction: 'desc' },
})

const initialSearch = computed(() =>
  typeof route.query.q === 'string' ? route.query.q : '',
)

if (initialSearch.value) {
  table.setSearch(initialSearch.value)
}

const highlightId = computed(() => {
  const raw = route.query.highlight
  if (typeof raw === 'string' && raw.trim()) {
    const parsed = Number(raw)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
})

const columns: ColumnDef<EventItem>[] = [
  { key: 'title', label: 'Название' },
  {
    key: 'event_date',
    label: 'Дата',
    getValue: (row) => row.event_date,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'employee_name',
    label: 'Сотрудник',
    getValue: (row) => row.employee_name ?? '—',
  },
  {
    key: 'event_type',
    label: 'Тип',
    getValue: (row) => row.event_type,
    format: (value) => labelEventType(value as string | null),
  },
  {
    key: 'source',
    label: 'Источник',
    getValue: (row) => row.source,
    format: (value) => labelEventSource(value as string | null),
  },
  {
    key: 'created_by',
    label: 'Создал',
    getValue: (row) => row.created_by ?? '—',
  },
  {
    key: 'status',
    label: 'Статус',
    getValue: (row) => row.status,
    format: (value) => getEventStatusMeta(value as string | null).label,
  },
  {
    key: 'actions',
    label: '',
    sortable: false,
    filterable: false,
  },
]

function onQueryUpdate(patch: Partial<TableQueryState>) {
  table.setQuery(patch)
}

async function complete(id: number) {
  if (!auth.canEdit()) return
  try {
    await api.completeEvent(id)
    toast.success('Мероприятие выполнено')
    await table.reload()
  } catch (err) {
    toast.error(err instanceof Error ? err.message : 'Не удалось выполнить мероприятие')
  }
}
</script>

<template>
  <section class="card page">
    <header><h2>Мероприятия</h2></header>
    <PageState
      :error="table.error.value"
      @retry="table.reload()"
    >
      <DataTable
        mode="server"
        table-id="events"
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
        :highlight-row-key="highlightId"
        search-placeholder="Поиск по мероприятиям..."
        @update:query="onQueryUpdate"
      >
        <template #cell-status="{ row }">
          <StatusBadge
            :label="getEventStatusMeta(row.status).label"
            :variant="getEventStatusMeta(row.status).variant"
          />
        </template>
        <template #cell-actions="{ row }">
          <button
            v-if="auth.canEdit() && row.status !== 'completed'"
            class="btn secondary"
            @click="complete(row.id)"
          >
            Выполнить
          </button>
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
