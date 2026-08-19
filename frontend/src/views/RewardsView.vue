<script setup lang="ts">
import { ref } from 'vue'
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

function startEdit(row: RewardRow) {
  editing.value = row
}

function cancelEdit() {
  editing.value = null
}

async function handleSaved() {
  editing.value = null
  await table.reload()
}
</script>

<template>
  <section class="card page">
    <header><h2>{{ MODULE_LABELS.rewards }}</h2></header>

    <RewardForm
      v-if="auth.canEdit()"
      :initial="editing"
      @saved="handleSaved"
      @cancel="cancelEdit"
    />

    <PageState
      :error="table.error.value"
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
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
  display: grid;
  gap: 1rem;
}
</style>
