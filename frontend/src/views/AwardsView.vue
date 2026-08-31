<script setup lang="ts">
import { ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import PageState from '@/components/PageState.vue'
import TenureAwardEditForm from '@/components/TenureAwardEditForm.vue'
import { api } from '@/api/client'
import { useServerTable } from '@/composables/useServerTable'
import type { ColumnDef } from '@/composables/useDataTable'
import type { Paginated, TableQueryState, TenureRow } from '@/types'
import { MODULE_LABELS } from '@/utils/labels'
import { formatNumericDate } from '@/utils/dates'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const editing = ref<TenureRow | null>(null)

type AwardYears = '10' | '15' | '20'

const table = useServerTable<TenureRow>({
  tableId: 'awards',
  fetcher: (params) => api.tenure(params) as Promise<Paginated<TenureRow>>,
  defaultSort: { key: 'tenure_years', direction: 'desc' },
})

function awardReceived(row: TenureRow, years: AwardYears): boolean {
  return Boolean(row.awards[years]?.is_received)
}

function awardCellClass(row: TenureRow, years: AwardYears) {
  if (awardReceived(row, years)) return 'award-cell-received'
  return undefined
}

function awardDisplayText(row: TenureRow, years: AwardYears): string {
  const award = row.awards[years]
  if (!award) return '—'
  if (award.is_received) {
    return award.received_date ? formatNumericDate(award.received_date) : '—'
  }
  if (award.milestone_date) return formatNumericDate(award.milestone_date)
  return '—'
}

function awardAriaLabel(row: TenureRow, years: AwardYears): string {
  const award = row.awards[years]
  if (!award) return `${years} лет: нет данных`
  if (award.is_received) {
    const date = award.received_date ? formatNumericDate(award.received_date) : 'дата не указана'
    return `${years} лет: получено ${date}`
  }
  if (award.milestone_date) {
    return `${years} лет: ${formatNumericDate(award.milestone_date)}`
  }
  return `${years} лет: нет данных`
}

function makeAwardColumn(years: AwardYears, label: string): ColumnDef<TenureRow> {
  return {
    key: `award_${years}`,
    label,
    sortable: false,
    getValue: (row) => awardDisplayText(row, years),
    cellClass: (row) => awardCellClass(row, years),
  }
}

const columns: ColumnDef<TenureRow>[] = [
  { key: 'full_name', label: 'ФИО' },
  {
    key: 'tenure_years',
    label: 'Стаж (всего)',
    getValue: (row) => row.tenure_years,
    format: (value) => `${value} лет`,
  },
  {
    key: 'continuous_tenure_years',
    label: 'Текущий период',
    getValue: (row) => row.continuous_tenure_years ?? row.tenure_years,
    format: (value) => `${value} лет`,
  },
  makeAwardColumn('10', '10 лет'),
  makeAwardColumn('15', '15 лет'),
  makeAwardColumn('20', '20 лет'),
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

function startEdit(row: TenureRow) {
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
    <header><h2>{{ MODULE_LABELS.awards }}</h2></header>

    <TenureAwardEditForm
      v-if="auth.canEdit() && editing"
      :row="editing"
      @saved="handleSaved"
      @cancel="cancelEdit"
    />

    <PageState
      :loading="table.loading.value"
      :refreshing="table.refreshing.value"
      :error="table.error.value"
      :has-data="table.rows.value.length > 0"
      @retry="table.reload()"
    >
      <DataTable
        mode="server"
        table-id="awards"
        :columns="columns"
        :rows="table.rows.value"
        :row-key="(row) => row.employment_id"
        :loading="table.loading.value"
        :total="table.total.value"
        :page="table.query.value.page"
        :per-page="table.query.value.per_page"
        :sort-key="table.query.value.sort"
        :sort-dir="table.query.value.direction"
        :search="table.query.value.q"
        :column-filters="table.query.value.columnFilters"
        search-placeholder="Поиск по наградам за стаж..."
        @update:query="onQueryUpdate"
      >
        <template #cell-award_10="{ row, display }">
          <span class="award-cell" :aria-label="awardAriaLabel(row, '10')">
            <span v-if="awardReceived(row, '10')" class="award-check" aria-hidden="true">✓</span>
            <span>{{ display }}</span>
          </span>
        </template>
        <template #cell-award_15="{ row, display }">
          <span class="award-cell" :aria-label="awardAriaLabel(row, '15')">
            <span v-if="awardReceived(row, '15')" class="award-check" aria-hidden="true">✓</span>
            <span>{{ display }}</span>
          </span>
        </template>
        <template #cell-award_20="{ row, display }">
          <span class="award-cell" :aria-label="awardAriaLabel(row, '20')">
            <span v-if="awardReceived(row, '20')" class="award-check" aria-hidden="true">✓</span>
            <span>{{ display }}</span>
          </span>
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

header h2 {
  margin: 0;
}

:deep(.award-cell-received) {
  background: #e8f7ef;
}

.award-cell {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  white-space: nowrap;
}

.award-check {
  color: var(--success);
  font-weight: 700;
  line-height: 1;
}
</style>
