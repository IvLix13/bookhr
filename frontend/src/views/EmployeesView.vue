<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import EmployeeForm from '@/components/EmployeeForm.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/api/client'
import type { ColumnDef } from '@/composables/useDataTable'
import type { Employee } from '@/types'
import { useAuthStore } from '@/stores/auth'
import { formatNumericDate } from '@/utils/dates'
import { getPassportStatusMeta } from '@/utils/statuses'

const auth = useAuthStore()
const employees = ref<Employee[]>([])
const loading = ref(true)
const editing = ref<Employee | null>(null)
const modalOpen = ref(false)
const error = ref('')

const columns: ColumnDef<Employee>[] = [
  {
    key: 'index',
    label: '№',
    sortable: false,
    filterable: false,
    getValue: (row) => employees.value.indexOf(row) + 1,
  },
  { key: 'full_name', label: 'ФИО' },
  { key: 'title', label: 'Должность' },
  {
    key: 'has_university',
    label: 'ВУЗ',
    getValue: (row) => (row.has_university ? 'Да' : 'Нет'),
  },
  {
    key: 'contract_end',
    label: 'Окончание Договора',
    getValue: (row) => row.contract_end,
    format: (value) => formatNumericDate(value as string | null),
    sortValue: (row) => row.contract_end,
  },
  {
    key: 'grade_date',
    label: 'Дата выдачи текущего грейды',
    getValue: (row) => row.grade_date,
    format: (value) => formatNumericDate(value as string | null),
    sortValue: (row) => row.grade_date,
  },
  {
    key: 'eligible_date',
    label: 'Дата доступности следующего грейды',
    getValue: (row) => row.eligible_date,
    format: (value) => formatNumericDate(value as string | null),
    sortValue: (row) => row.eligible_date,
  },
  {
    key: 'hire_date',
    label: 'Начало работы',
    getValue: (row) => row.hire_date,
    format: (value) => formatNumericDate(value as string | null),
    sortValue: (row) => row.hire_date,
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
    format: (value) => formatNumericDate(value as string | null),
    sortValue: (row) => row.passport_until,
  },
  {
    key: 'actions',
    label: '',
    sortable: false,
    filterable: false,
  },
]

async function loadEmployees() {
  employees.value = (await api.fetchAllEmployees()) as Employee[]
}

onMounted(async () => {
  await loadEmployees()
  loading.value = false
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})

function openCreate() {
  editing.value = null
  error.value = ''
  modalOpen.value = true
}

function startEdit(row: Employee) {
  editing.value = row
  error.value = ''
  modalOpen.value = true
}

function closeModal() {
  modalOpen.value = false
  editing.value = null
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && modalOpen.value) {
    closeModal()
  }
}

async function handleSaved() {
  closeModal()
  error.value = ''
  await loadEmployees()
}

async function removeEmployee(row: Employee) {
  const name = row.full_name ?? `ID ${row.id}`
  if (!window.confirm(`Удалить сотрудника «${name}»? Связанные автособытия также будут удалены.`)) {
    return
  }
  error.value = ''
  try {
    await api.deleteEmployee(row.id)
    if (editing.value?.id === row.id) {
      closeModal()
    }
    await loadEmployees()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Не удалось удалить сотрудника'
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

    <p v-if="error" class="error">{{ error }}</p>

    <DataTable
      :columns="columns"
      :rows="employees"
      row-key="id"
      :loading="loading"
      search-placeholder="Поиск по сотрудникам..."
    >
      <template #cell-index="{ row }">
        {{ employees.indexOf(row) + 1 }}
      </template>
      <template #cell-passport="{ row }">
        <StatusBadge
          :label="formatNumericDate(row.passport_until)"
          :variant="getPassportStatusMeta(row.passport_status).variant"
        />
      </template>
      <template #cell-actions="{ row }">
        <div v-if="auth.canEdit()" class="row-actions">
          <button class="btn secondary" type="button" @click="startEdit(row)">
            Изменить
          </button>
          <button class="btn ghost" type="button" @click="removeEmployee(row)">
            Удалить
          </button>
        </div>
      </template>
    </DataTable>

    <Teleport to="body">
      <div
        v-if="modalOpen && auth.canEdit()"
        class="overlay"
        @click.self="closeModal"
      >
        <section
          class="card modal"
          role="dialog"
          aria-modal="true"
          :aria-label="editing ? 'Редактирование сотрудника' : 'Новый сотрудник'"
        >
          <header class="modal-header">
            <h3>{{ editing ? 'Редактирование сотрудника' : 'Новый сотрудник' }}</h3>
            <button class="btn ghost" type="button" aria-label="Закрыть" @click="closeModal">
              ×
            </button>
          </header>
          <EmployeeForm
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

.row-actions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
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

:deep(.form h3) {
  display: none;
}
</style>
