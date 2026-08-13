<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DataTable from '@/components/DataTable.vue'
import EventDetailModal from '@/components/EventDetailModal.vue'
import PageState from '@/components/PageState.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/api/client'
import { useServerTable } from '@/composables/useServerTable'
import { useToast } from '@/composables/useToast'
import type { ColumnDef } from '@/composables/useDataTable'
import type { EventItem, Paginated, TableQueryState } from '@/types'
import { formatShortDate } from '@/utils/dates'
import { labelEventSource, labelEventType } from '@/utils/labels'
import { getEventStatusMeta, resolveEventStatus } from '@/utils/statuses'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
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

const openEventId = computed(() => {
  const raw = route.query.event
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
    getValue: (row) => resolveEventStatus(row.status, row.effective_status),
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

function openEvent(id: number) {
  router.replace({ query: { ...route.query, event: String(id) } })
}

function closeEventModal() {
  const nextQuery = { ...route.query }
  delete nextQuery.event
  router.replace({ query: nextQuery })
}

function onRowClick(row: EventItem) {
  openEvent(row.id)
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

async function onEventChanged() {
  await table.reload()
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
        row-clickable
        :loading="table.loading.value"
        :total="table.total.value"
        :page="table.query.value.page"
        :per-page="table.query.value.per_page"
        :sort-key="table.query.value.sort"
        :sort-dir="table.query.value.direction"
        :search="table.query.value.q"
        :column-filters="table.query.value.columnFilters"
        search-placeholder="Поиск по мероприятиям..."
        @update:query="onQueryUpdate"
        @row-click="onRowClick"
      >
        <template #cell-status="{ row }">
          <StatusBadge
            :label="getEventStatusMeta(resolveEventStatus(row.status, row.effective_status)).label"
            :variant="getEventStatusMeta(resolveEventStatus(row.status, row.effective_status)).variant"
          />
        </template>
        <template #cell-actions="{ row }">
          <button
            v-if="auth.canEdit() && resolveEventStatus(row.status, row.effective_status) !== 'completed' && row.status !== 'cancelled'"
            class="btn secondary"
            type="button"
            @click.stop="complete(row.id)"
          >
            Выполнить
          </button>
        </template>
      </DataTable>
    </PageState>

    <EventDetailModal
      :open="openEventId != null"
      :event-id="openEventId"
      @close="closeEventModal"
      @changed="onEventChanged"
    />
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
}
</style>
