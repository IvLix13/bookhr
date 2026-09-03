<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import ContractEditForm from '@/components/ContractEditForm.vue'
import DataTable from '@/components/DataTable.vue'
import EventDetailModal from '@/components/EventDetailModal.vue'
import PageState from '@/components/PageState.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/api/client'
import { useServerTable } from '@/composables/useServerTable'
import type { ColumnDef } from '@/composables/useDataTable'
import type { ContractRow, Paginated, TableQueryState } from '@/types'
import { useAuthStore } from '@/stores/auth'
import { formatLocalDate, formatShortDate } from '@/utils/dates'
import { MODULE_LABELS } from '@/utils/labels'
import { getContractReportDisplayMeta } from '@/utils/statuses'

const auth = useAuthStore()
const editing = ref<ContractRow | null>(null)
const modalOpen = ref(false)

const table = useServerTable<ContractRow>({
  tableId: 'contracts',
  fetcher: (params) => api.contracts(params) as Promise<Paginated<ContractRow>>,
  defaultSort: { key: 'end_date', direction: 'asc' },
})

const todayIso = formatLocalDate(new Date())

const columns: ColumnDef<ContractRow>[] = [
  { key: 'full_name', label: 'ФИО' },
  {
    key: 'term_years',
    label: 'Срок (лет)',
    getValue: (row) => row.term_years,
    format: (value) => (value ? `${value} г.` : '—'),
  },
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
    sortable: false,
    getValue: (row) => reportDate(row),
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'report_status',
    label: 'Статус рапорта',
    sortable: false,
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

/** Once the report is done its completion date is the date of the report. */
function reportDate(row: ContractRow): string | null {
  const event = row.renewal_report_event
  if (!event) return null
  return event.completed_date ?? event.event_date
}

const openEventId = ref<number | null>(null)

function openReportEvent(id: number) {
  openEventId.value = id
}

function closeReportEvent() {
  openEventId.value = null
}

async function onReportChanged() {
  await table.reload()
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && modalOpen.value) {
    closeModal()
  }
}

window.addEventListener('keydown', onKeydown)
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})

function startEdit(row: ContractRow) {
  if (!auth.canEdit()) return
  editing.value = row
  modalOpen.value = true
}

function closeModal() {
  modalOpen.value = false
  editing.value = null
}

async function handleSaved() {
  closeModal()
  await table.reload()
}
</script>

<template>
  <section class="card page">
    <header><h2>{{ MODULE_LABELS.contracts }}</h2></header>

    <PageState
      :loading="table.loading.value"
      :refreshing="table.refreshing.value"
      :error="table.error.value"
      :has-data="table.rows.value.length > 0"
      @retry="table.reload()"
    >
      <DataTable
        mode="server"
        table-id="contracts"
        :columns="columns"
        :rows="table.rows.value"
        row-key="id"
        :row-clickable="auth.canEdit()"
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
        @row-click="startEdit"
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
          <button
            v-if="row.renewal_report_event"
            type="button"
            class="btn secondary"
            @click.stop="openReportEvent(row.renewal_report_event.id)"
          >
            Мероприятие
          </button>
        </template>
      </DataTable>
    </PageState>

    <EventDetailModal
      :open="openEventId != null"
      :event-id="openEventId"
      @close="closeReportEvent"
      @changed="onReportChanged"
    />

    <Teleport to="body">
      <div
        v-if="modalOpen && editing"
        class="overlay"
        @click.self="closeModal"
      >
        <section
          class="card modal"
          role="dialog"
          aria-modal="true"
          aria-label="Редактирование договора"
        >
          <header class="modal-header">
            <h3>Редактирование договора: {{ editing.full_name ?? 'Сотрудник' }}</h3>
            <button class="btn ghost" type="button" aria-label="Закрыть" @click="closeModal">
              ×
            </button>
          </header>
          <ContractEditForm
            compact
            :row="editing"
            @saved="handleSaved"
            @cancel="closeModal"
          />
        </section>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
  display: grid;
  gap: 1rem;
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
  width: min(720px, 100%);
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
