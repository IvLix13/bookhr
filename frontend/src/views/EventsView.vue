<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/api/client'
import type { ColumnDef } from '@/composables/useDataTable'
import type { EventItem } from '@/types'
import { formatShortDate } from '@/utils/dates'
import { getEventStatusMeta } from '@/utils/statuses'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const events = ref<EventItem[]>([])
const loading = ref(true)

const columns: ColumnDef<EventItem>[] = [
  { key: 'title', label: 'Название' },
  {
    key: 'event_date',
    label: 'Дата',
    getValue: (row) => row.event_date,
    format: (value) => formatShortDate(value as string | null),
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

onMounted(async () => {
  events.value = (await api.fetchAllEvents()) as EventItem[]
  loading.value = false
})

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
</style>
