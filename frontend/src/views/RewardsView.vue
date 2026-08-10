<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import RewardForm from '@/components/RewardForm.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/api/client'
import type { ColumnDef } from '@/composables/useDataTable'
import type { RewardRow } from '@/types'
import { formatNumericDate } from '@/utils/dates'
import { getRewardStatusMeta } from '@/utils/statuses'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const rows = ref<RewardRow[]>([])
const loading = ref(true)
const editing = ref<RewardRow | null>(null)

const columns: ColumnDef<RewardRow>[] = [
  { key: 'full_name', label: 'ФИО' },
  { key: 'reward_type', label: 'Вид поощрения' },
  {
    key: 'status',
    label: 'Состояние',
    getValue: (row) => row.status,
    format: (value) => getRewardStatusMeta(value as string).label,
    sortValue: (row) => row.status,
  },
  {
    key: 'updated_at',
    label: 'Дата изменения',
    getValue: (row) => row.updated_at,
    format: (value) => formatNumericDate((value as string | null)?.slice(0, 10) ?? null),
    sortValue: (row) => row.updated_at,
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
    format: (value) => formatNumericDate(value as string | null),
    sortValue: (row) => row.delivered_date,
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

async function loadRewards() {
  rows.value = (await api.rewards()) as RewardRow[]
}

onMounted(async () => {
  await loadRewards()
  loading.value = false
})

function startEdit(row: RewardRow) {
  editing.value = row
}

function cancelEdit() {
  editing.value = null
}

async function handleSaved() {
  editing.value = null
  await loadRewards()
}
</script>

<template>
  <section class="card page">
    <header><h2>Поощрения</h2></header>

    <RewardForm
      v-if="auth.canEdit()"
      :initial="editing"
      @saved="handleSaved"
      @cancel="cancelEdit"
    />

    <DataTable
      :columns="columns"
      :rows="rows"
      row-key="id"
      :loading="loading"
      search-placeholder="Поиск по поощрениям..."
    >
      <template #cell-status="{ row }">
        <StatusBadge
          :label="getRewardStatusMeta(row.status).label"
          :variant="getRewardStatusMeta(row.status).variant"
        />
      </template>
      <template #cell-updated_at="{ row }">
        {{ formatNumericDate(row.updated_at?.slice(0, 10) ?? null) }}
      </template>
      <template #cell-delivered_date="{ row }">
        {{ formatNumericDate(row.delivered_date) }}
      </template>
      <template #cell-actions="{ row }">
        <button
          v-if="auth.canEdit()"
          class="btn secondary"
          @click="startEdit(row)"
        >
          Изменить
        </button>
      </template>
    </DataTable>
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
  display: grid;
  gap: 1rem;
}
</style>
