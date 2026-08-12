<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import DataTable from '@/components/DataTable.vue'
import GradeAssignForm from '@/components/GradeAssignForm.vue'
import PageState from '@/components/PageState.vue'
import { api } from '@/api/client'
import { useServerTable } from '@/composables/useServerTable'
import type { ColumnDef } from '@/composables/useDataTable'
import type { GradeRow, Paginated, TableQueryState } from '@/types'
import { formatShortDate } from '@/utils/dates'
import { MODULE_LABELS } from '@/utils/labels'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const editing = ref<GradeRow | null>(null)

const table = useServerTable<GradeRow>({
  tableId: 'grades',
  fetcher: (params) => api.grades(params) as Promise<Paginated<GradeRow>>,
  defaultSort: { key: 'full_name', direction: 'asc' },
})

const columns: ColumnDef<GradeRow>[] = [
  { key: 'full_name', label: 'ФИО' },
  {
    key: 'grade',
    label: 'Текущий грейд',
    getValue: (row) => row.grade?.name ?? '—',
  },
  {
    key: 'grade_date',
    label: 'Дата выдачи',
    getValue: (row) => row.grade_date,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'next_grade',
    label: 'Следующий грейд',
    getValue: (row) => row.next_grade?.name ?? '—',
  },
  {
    key: 'eligible_date',
    label: 'Дата доступности',
    getValue: (row) => row.eligible_date,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'days_left',
    label: 'Осталось дней',
    getValue: (row) => row.days_left,
    format: (value) => (value == null ? '—' : String(value)),
  },
  {
    key: 'actions',
    label: '',
    sortable: false,
    filterable: false,
  },
]

const pageHint = computed(
  () =>
    'Таблица активных сотрудников с назначенными грейдами. Записи справочника появляются здесь после назначения сотруднику.',
)

function onQueryUpdate(patch: Partial<TableQueryState>) {
  table.setQuery(patch)
}

function startAssign(row: GradeRow) {
  editing.value = row
}

function cancelAssign() {
  editing.value = null
}

async function handleSaved() {
  editing.value = null
  await table.reload()
}
</script>

<template>
  <section class="card page">
    <header class="page-header">
      <div>
        <h2>Грейды</h2>
        <p class="hint">{{ pageHint }}</p>
      </div>
      <RouterLink class="btn secondary" to="/grade-catalog">
        {{ MODULE_LABELS.gradeCatalog }}
      </RouterLink>
    </header>

    <GradeAssignForm
      v-if="auth.canEdit()"
      :initial="editing"
      @saved="handleSaved"
      @cancel="cancelAssign"
    />

    <PageState
      :error="table.error.value"
      @retry="table.reload()"
    >
      <DataTable
        mode="server"
        table-id="grades"
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
        search-placeholder="Поиск по ФИО..."
        @update:query="onQueryUpdate"
      >
        <template #cell-actions="{ row }">
          <button
            v-if="auth.canEdit()"
            class="btn secondary"
            type="button"
            @click="startAssign(row)"
          >
            {{ row.grade ? 'Изменить грейд' : 'Назначить грейд' }}
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

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  flex-wrap: wrap;
}

.page-header h2 {
  margin: 0;
}

.hint {
  margin: 0.35rem 0 0;
  color: var(--muted);
  max-width: 52rem;
}
</style>
