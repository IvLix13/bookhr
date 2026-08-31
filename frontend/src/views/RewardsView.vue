<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import PageState from '@/components/PageState.vue'
import RewardForm from '@/components/RewardForm.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/api/client'
import { useServerTable } from '@/composables/useServerTable'
import type { ColumnDef } from '@/composables/useDataTable'
import type { Paginated, RewardRow, TableQueryState } from '@/types'
import { formatShortDate } from '@/utils/dates'
import { MODULE_LABELS } from '@/utils/labels'
import { getRewardStatusMeta } from '@/utils/statuses'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const editing = ref<RewardRow | null>(null)
const modalOpen = ref(false)

const table = useServerTable<RewardRow>({
  tableId: 'rewards',
  fetcher: (params) => api.rewards(params) as Promise<Paginated<RewardRow>>,
  defaultSort: { key: 'status_changed_date', direction: 'desc' },
})

const columns: ColumnDef<RewardRow>[] = [
  { key: 'full_name', label: 'ФИО' },
  { key: 'reward_type', label: 'Вид поощрения' },
  {
    key: 'status',
    label: 'Состояние',
    getValue: (row) => row.status,
    format: (value) => getRewardStatusMeta(value as string).label,
  },
  {
    key: 'status_changed_date',
    label: 'Дата изменения',
    getValue: (row) => row.status_changed_date ?? row.updated_at?.slice(0, 10) ?? null,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'directive_text',
    label: 'Указание на вручение',
    getValue: (row) => row.directive_text ?? '—',
  },
  {
    key: 'delivered_date',
    label: 'Дата вручения',
    getValue: (row) => row.delivered_date,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'notes',
    label: 'Примечание',
    getValue: (row) => row.notes ?? '—',
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

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && modalOpen.value) {
    closeModal()
  }
}

window.addEventListener('keydown', onKeydown)
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})

function openCreate() {
  if (!auth.canEdit()) return
  editing.value = null
  modalOpen.value = true
}

function startEdit(row: RewardRow) {
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
    <header class="page-header">
      <h2>{{ MODULE_LABELS.rewards }}</h2>
      <button
        v-if="auth.canEdit()"
        class="btn"
        type="button"
        @click="openCreate"
      >
        Добавить новое поощрение
      </button>
    </header>

    <PageState
      :loading="table.loading.value"
      :refreshing="table.refreshing.value"
      :error="table.error.value"
      :has-data="table.rows.value.length > 0"
      @retry="table.reload()"
    >
      <DataTable
        mode="server"
        table-id="rewards"
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
        default-sort-key="status_changed_date"
        default-sort-dir="desc"
        search-placeholder="Поиск по поощрениям..."
        @update:query="onQueryUpdate"
      >
        <template #cell-status="{ row }">
          <StatusBadge
            :label="getRewardStatusMeta(row.status).label"
            :variant="getRewardStatusMeta(row.status).variant"
          />
        </template>
        <template #cell-actions="{ row }">
          <button
            v-if="auth.canEdit()"
            class="btn secondary"
            type="button"
            @click="startEdit(row)"
          >
            Изменить
          </button>
        </template>
      </DataTable>
    </PageState>

    <Teleport to="body">
      <div
        v-if="modalOpen"
        class="overlay"
        @click.self="closeModal"
      >
        <section
          class="card modal"
          role="dialog"
          aria-modal="true"
          :aria-label="editing ? 'Редактирование поощрения' : 'Новое поощрение'"
        >
          <header class="modal-header">
            <h3>{{ editing ? 'Редактирование поощрения' : 'Новое поощрение' }}</h3>
            <button class="btn ghost" type="button" aria-label="Закрыть" @click="closeModal">
              ×
            </button>
          </header>
          <RewardForm
            compact
            :initial="editing"
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

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
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

:deep(.form h3) {
  display: none;
}
</style>
