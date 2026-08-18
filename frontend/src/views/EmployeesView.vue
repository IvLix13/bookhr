<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import DataTable from '@/components/DataTable.vue'
import EmployeeForm from '@/components/EmployeeForm.vue'
import PageState from '@/components/PageState.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/api/client'
import { useServerTable } from '@/composables/useServerTable'
import type { ColumnDef } from '@/composables/useDataTable'
import type { Employee, Paginated, TableQueryState } from '@/types'
import { useAuthStore } from '@/stores/auth'
import { formatShortDate } from '@/utils/dates'
import { getPassportStatusMeta, getRewardStatusMeta } from '@/utils/statuses'

const route = useRoute()
const auth = useAuthStore()

const table = useServerTable<Employee>({
  tableId: 'employees',
  fetcher: (params) => api.employees(params) as Promise<Paginated<Employee>>,
  defaultSort: { key: 'hire_date', direction: 'desc' },
})

const initialSearch = computed(() =>
  typeof route.query.q === 'string' ? route.query.q : '',
)

if (initialSearch.value) {
  table.setSearch(initialSearch.value)
}

const editing = ref<Employee | null>(null)
const modalOpen = ref(false)
const actionError = ref('')

const formReadonly = computed(() => !auth.canEdit())

const columns: ColumnDef<Employee>[] = [
  {
    key: 'index',
    label: '№',
    sortable: false,
    filterable: false,
  },
  { key: 'full_name', label: 'ФИО' },
  { key: 'title', label: 'Должность' },
  {
    key: 'education_status',
    label: 'ВУЗ',
    getValue: (row) => {
      if (row.education_status === 'yes') return 'Да'
      if (row.education_status === 'no') return 'Нет'
      return 'Неизвестно'
    },
  },
  {
    key: 'contract_end',
    label: 'Окончание Договора',
    getValue: (row) => row.contract_end,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'grade_date',
    label: 'Дата выдачи текущего грейды',
    getValue: (row) => row.grade_date,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'eligible_date',
    label: 'Дата доступности следующего грейды',
    getValue: (row) => row.eligible_date,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'hire_date',
    label: 'Начало работы',
    getValue: (row) => row.hire_date,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'tenure_years',
    label: 'Стаж',
    getValue: (row) => row.tenure_years,
    format: (value) => `${value} лет`,
  },
  {
    key: 'passport',
    label: 'Паспорт',
    getValue: (row) => row.passport_until,
    format: (value) => formatShortDate(value as string | null),
  },
  {
    key: 'reward_status',
    label: 'Поощрение',
    getValue: (row) => row.reward_status,
    format: (value) => getRewardStatusMeta(value as string | null).label,
    sortable: false,
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
  actionError.value = ''
  modalOpen.value = true
}

function openEmployee(row: Employee) {
  editing.value = row
  actionError.value = ''
  modalOpen.value = true
}

function closeModal() {
  modalOpen.value = false
  editing.value = null
}

async function handleSaved() {
  closeModal()
  actionError.value = ''
  await table.reload()
}

async function removeEmployee() {
  if (!editing.value || !auth.canEdit()) return
  const row = editing.value
  const name = row.full_name ?? `ID ${row.id}`
  if (!window.confirm(`Удалить сотрудника «${name}»? Связанные автособытия также будут удалены.`)) {
    return
  }
  actionError.value = ''
  try {
    await api.deleteEmployee(row.id)
    closeModal()
    await table.reload()
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : 'Не удалось удалить сотрудника'
  }
}
</script>

<template>
  <section class="card page">
    <header class="page-header">
      <h2>Общая таблица сотрудников</h2>
      <button
        v-if="auth.canEdit()"
        class="btn"
        type="button"
        @click="openCreate"
      >
        Добавить сотрудника
      </button>
    </header>

    <p v-if="actionError" class="error">{{ actionError }}</p>

    <PageState
      :error="table.error.value"
      @retry="table.reload()"
    >
      <DataTable
        mode="server"
        table-id="employees"
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
        search-placeholder="Поиск по сотрудникам..."
        @update:query="onQueryUpdate"
        @row-click="openEmployee"
      >
        <template #cell-index="{ row }">
          {{
            (table.query.value.page - 1) * table.query.value.per_page +
            table.rows.value.indexOf(row) +
            1
          }}
        </template>
        <template #cell-passport="{ row }">
          <StatusBadge
            :label="formatShortDate(row.passport_until)"
            :variant="getPassportStatusMeta(row.passport_status).variant"
          />
        </template>
        <template #cell-reward_status="{ row }">
          <StatusBadge
            :label="getRewardStatusMeta(row.reward_status).label"
            :variant="getRewardStatusMeta(row.reward_status).variant"
          />
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
          :aria-label="editing ? 'Карточка сотрудника' : 'Новый сотрудник'"
        >
          <header class="modal-header">
            <h3>
              {{
                editing
                  ? formReadonly
                    ? 'Карточка сотрудника'
                    : 'Редактирование сотрудника'
                  : 'Новый сотрудник'
              }}
            </h3>
            <div class="modal-header-actions">
              <button
                v-if="auth.canEdit() && editing"
                class="btn ghost danger"
                type="button"
                @click="removeEmployee"
              >
                Удалить
              </button>
              <button class="btn ghost" type="button" aria-label="Закрыть" @click="closeModal">
                ×
              </button>
            </div>
          </header>
          <EmployeeForm
            :initial="editing"
            :readonly="formReadonly && Boolean(editing)"
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
}

.page-header {
  display: grid;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.page-header h2 {
  margin: 0;
}

.page-header .btn {
  justify-self: start;
}

.error {
  margin: 0 0 0.75rem;
  color: var(--danger);
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
  width: min(760px, 100%);
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

.modal-header-actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.btn.danger {
  color: var(--danger);
}

:deep(.form h3) {
  display: none;
}
</style>
