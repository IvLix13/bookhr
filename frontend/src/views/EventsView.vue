<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DataTable from '@/components/DataTable.vue'
import EventDetailModal from '@/components/EventDetailModal.vue'
import EventForm from '@/components/EventForm.vue'
import PageState from '@/components/PageState.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/api/client'
import { useServerTable } from '@/composables/useServerTable'
import { useToast } from '@/composables/useToast'
import type { ColumnDef } from '@/composables/useDataTable'
import type { EventItem, Paginated, TableQueryState } from '@/types'
import { formatLocalDate, formatShortDate } from '@/utils/dates'
import { MODULE_LABELS, labelEventSource, labelEventType } from '@/utils/labels'
import { getEventStatusMeta, resolveEventStatus } from '@/utils/statuses'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const toast = useToast()

const completingId = ref<number | null>(null)

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

const initialStatus = computed(() =>
  typeof route.query.status === 'string' ? route.query.status : '',
)

if (initialStatus.value) {
  table.setQuery({ columnFilters: { ...table.query.value.columnFilters, status: initialStatus.value } })
}

watch(
  () => route.query.status,
  (status) => {
    if (typeof status === 'string' && status) {
      table.setQuery({
        columnFilters: { ...table.query.value.columnFilters, status },
        page: 1,
      })
    }
  },
)

const openEventId = computed(() => {
  const raw = route.query.event
  if (typeof raw === 'string' && raw.trim()) {
    const parsed = Number(raw)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
})

const createOpen = computed(() => auth.canEdit() && route.query.create === '1')
const createInitialDate = formatLocalDate(new Date())

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
  if (patch.columnFilters?.status !== undefined) {
    const nextQuery = { ...route.query }
    const status = patch.columnFilters.status?.trim()
    if (status) nextQuery.status = status
    else delete nextQuery.status
    router.replace({ query: nextQuery })
  }
}

function openEvent(id: number) {
  router.replace({ query: { ...route.query, event: String(id) } })
}

function closeEventModal() {
  const nextQuery = { ...route.query }
  delete nextQuery.event
  router.replace({ query: nextQuery })
}

function openCreate() {
  if (!auth.canEdit()) return
  router.replace({ query: { ...route.query, create: '1' } })
}

function closeCreate() {
  const nextQuery = { ...route.query }
  delete nextQuery.create
  router.replace({ query: nextQuery })
}

function onRowClick(row: EventItem) {
  openEvent(row.id)
}

async function complete(id: number) {
  if (!auth.canEdit() || completingId.value != null) return
  completingId.value = id
  try {
    await api.completeEvent(id)
    toast.success('Мероприятие выполнено')
    await table.reload()
  } catch (err) {
    toast.error(err instanceof Error ? err.message : 'Не удалось выполнить мероприятие')
  } finally {
    completingId.value = null
  }
}

function completeOrChoose(row: EventItem) {
  if (
    row.grade_completion?.requires_selection ||
    row.grade_completion?.blocked_reason
  ) {
    openEvent(row.id)
    return
  }
  void complete(row.id)
}

async function onEventChanged() {
  await table.reload()
}

async function onCreated() {
  toast.success('Событие создано')
  closeCreate()
  await table.reload()
}
</script>

<template>
  <section class="card page">
    <header class="page-header">
      <h2>Мероприятия</h2>
      <button
        v-if="auth.canEdit()"
        class="btn"
        type="button"
        @click="openCreate"
      >
        {{ MODULE_LABELS.eventCreate }}
      </button>
    </header>
    <PageState
      :error="table.error.value"
      :refreshing="table.refreshing.value"
      :has-data="table.rows.value.length > 0"
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
            :disabled="completingId === row.id"
            @click.stop="completeOrChoose(row)"
          >
            {{ completingId === row.id ? 'Сохранение...' : 'Выполнить' }}
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

    <Teleport to="body">
      <div
        v-if="createOpen"
        class="overlay"
        @click.self="closeCreate"
      >
        <section
          class="card modal"
          role="dialog"
          aria-modal="true"
          aria-label="Создать мероприятие"
        >
          <header class="modal-header">
            <h3>{{ MODULE_LABELS.eventCreate }}</h3>
            <button class="btn ghost" type="button" aria-label="Закрыть" @click="closeCreate">
              ×
            </button>
          </header>
          <EventForm
            compact
            :initial-date="createInitialDate"
            @created="onCreated"
            @cancel="closeCreate"
          />
        </section>
      </div>
    </Teleport>
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
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.page-header h2 {
  margin: 0;
}

.overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: grid;
  place-items: center;
  padding: 1rem;
  z-index: 1000;
}

.modal {
  width: min(560px, 100%);
  max-height: calc(100vh - 2rem);
  overflow: auto;
  padding: 1rem;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.modal-header h3 {
  margin: 0;
}
</style>
