<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
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
const modalOpen = ref(false)

const table = useServerTable<GradeRow>({
  tableId: 'grades',
  schemaVersion: 2,
  fetcher: (params) => api.grades(params) as Promise<Paginated<GradeRow>>,
  defaultSort: { key: 'eligible_date_nearest', direction: 'asc' },
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
    key: 'next_grade_candidates',
    label: 'Следующий грейд',
    sortable: false,
    getValue: (row) => {
      const candidates = row.next_grade_candidates ?? []
      return candidates.length ? candidates.map((grade) => grade.name).join(', ') : '—'
    },
  },
  {
    key: 'eligible_date',
    label: 'Дата доступности',
    sortKey: 'eligible_date_nearest',
    getValue: (row) => row.eligible_date,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'days_left',
    label: 'Осталось дней',
    getValue: (row) => row.days_left,
    format: (value) => (value == null ? '—' : String(value)),
  },
]

const pageHint = computed(
  () =>
    'Таблица активных сотрудников с назначенными грейдами. Записи справочника появляются здесь после назначения сотруднику.',
)

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

function startAssign(row: GradeRow) {
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
    <header class="page-header">
      <div>
        <h2>Грейды</h2>
        <p class="hint">{{ pageHint }}</p>
      </div>
      <RouterLink class="btn secondary" to="/grade-catalog">
        {{ MODULE_LABELS.gradeCatalog }}
      </RouterLink>
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
        table-id="grades"
        :columns="columns"
        :rows="table.rows.value"
        :row-key="(row) => row.employment_id"
        :row-clickable="auth.canEdit()"
        :loading="table.loading.value"
        :total="table.total.value"
        :page="table.query.value.page"
        :per-page="table.query.value.per_page"
        :sort-key="table.query.value.sort"
        :sort-dir="table.query.value.direction"
        :search="table.query.value.q"
        :column-filters="table.query.value.columnFilters"
        default-sort-key="eligible_date_nearest"
        default-sort-dir="asc"
        search-placeholder="Поиск по ФИО..."
        @update:query="onQueryUpdate"
        @row-click="startAssign"
      >
        <template #cell-eligible_date="{ row, display }">
          <span v-if="!row.eligible_date">—</span>
          <span v-else class="eligible-cell">
            {{ display }}
            <span v-if="row.is_available" class="badge success">Доступен</span>
          </span>
        </template>
      </DataTable>
    </PageState>

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
          :aria-label="editing.grade ? 'Изменить грейд' : 'Назначить грейд'"
        >
          <header class="modal-header">
            <div>
              <h3>{{ editing.grade ? 'Изменить грейд' : 'Назначить грейд' }}</h3>
              <p>{{ editing.full_name }}</p>
            </div>
            <button class="btn ghost" type="button" aria-label="Закрыть" @click="closeModal">
              ×
            </button>
          </header>
          <GradeAssignForm
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

.eligible-cell {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  white-space: nowrap;
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
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.modal-header h3 {
  margin: 0;
}

.modal-header p {
  margin: 0.35rem 0 0;
  color: var(--muted);
}
</style>
