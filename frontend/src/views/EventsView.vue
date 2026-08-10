<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/api/client'
import type { ColumnDef } from '@/composables/useDataTable'
import type { EventItem } from '@/types'
import { formatNumericDate } from '@/utils/dates'
import { getEventStatusMeta } from '@/utils/statuses'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const events = ref<EventItem[]>([])
const loading = ref(true)

const highlightId = computed(() => {
  const raw = route.query.highlight
  return typeof raw === 'string' ? Number(raw) : null
})

const columns: ColumnDef<EventItem>[] = [
  { key: 'title', label: 'Название' },
  {
    key: 'event_date',
    label: 'Дата',
    getValue: (row) => row.event_date,
    format: (value) => formatNumericDate(value as string | null),
    sortValue: (row) => row.event_date,
  },
  {
    key: 'employee_name',
    label: 'Сотрудник',
    getValue: (row) => row.employee_name ?? '—',
  },
  { key: 'event_type', label: 'Тип' },
  { key: 'source', label: 'Источник' },
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
    sortValue: (row) => row.status,
  },
  {
    key: 'actions',
    label: '',
    sortable: false,
    filterable: false,
  },
]

async function loadEvents() {
  events.value = (await api.fetchAllEvents()) as EventItem[]
}

onMounted(async () => {
  await loadEvents()
  loading.value = false
  scrollToHighlight()
})

watch(highlightId, () => {
  scrollToHighlight()
})

function scrollToHighlight() {
  if (!highlightId.value) return
  requestAnimationFrame(() => {
    const row = document.querySelector(`[data-event-id="${highlightId.value}"]`)
    row?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  })
}

function rowClass(row: EventItem) {
  return highlightId.value === row.id ? 'highlighted' : undefined
}

function rowAttrs(row: EventItem) {
  return { 'data-event-id': row.id }
}

async function complete(id: number) {
  if (!auth.canEdit()) return
  await api.completeEvent(id)
  events.value = events.value.map((event: EventItem) =>
    event.id === id ? { ...event, status: 'completed' } : event,
  )
}
</script>

<template>
  <section class="card page">
    <header><h2>Мероприятия</h2></header>
    <DataTable
      :columns="columns"
      :rows="events"
      row-key="id"
      :loading="loading"
      :row-class="rowClass"
      :row-attrs="rowAttrs"
      search-placeholder="Поиск по мероприятиям..."
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
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
}

:deep(.highlighted) {
  outline: 2px solid var(--accent, #2f6fed);
  outline-offset: -2px;
}
</style>
