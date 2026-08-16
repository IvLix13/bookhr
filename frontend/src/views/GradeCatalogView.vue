<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import DataTable from '@/components/DataTable.vue'
import GradeCatalogForm from '@/components/GradeCatalogForm.vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import type { ColumnDef } from '@/composables/useDataTable'
import type { Grade } from '@/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const grades = ref<Grade[]>([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const editing = ref<Grade | null>(null)
const pendingDelete = ref<Grade | null>(null)

const columns: ColumnDef<Grade>[] = [
  { key: 'name', label: 'Название' },
  { key: 'rank', label: 'Ранг' },
  {
    key: 'min_years',
    label: 'Мин. лет',
    getValue: (row) => row.min_years,
    format: (value) => String(value),
  },
  {
    key: 'extra_year_without_university',
    label: 'Без ВУЗа',
    getValue: (row) => (row.extra_year_without_university ? '+1 год' : 'Без надбавки'),
  },
  {
    key: 'is_active',
    label: 'Статус',
    sortable: false,
    filterable: false,
  },
  {
    key: 'actions',
    label: '',
    sortable: false,
    filterable: false,
  },
]

const deleteTitle = computed(() =>
  pendingDelete.value ? `Удалить грейд «${pendingDelete.value.name}»?` : 'Удалить грейд?',
)

const deleteMessage = computed(() => {
  const grade = pendingDelete.value
  if (!grade) return ''
  const count = grade.in_use_count ?? 0
  if (count <= 0) {
    return 'Грейд будет удалён из справочника.'
  }
  const noun = employeeNoun(count)
  return `Этот грейд используется у ${count} ${noun}. Если удалить его, в поле грейда у сотрудников будет «—».`
})

function employeeNoun(count: number): string {
  const abs = Math.abs(count) % 100
  const last = abs % 10
  if (abs > 10 && abs < 20) return 'сотрудников'
  if (last === 1) return 'сотрудника'
  return 'сотрудников'
}

async function loadGrades() {
  grades.value = (await api.gradeCatalog()) as Grade[]
}

function startEdit(grade: Grade) {
  editing.value = grade
}

async function onSaved() {
  await loadGrades()
  editing.value = null
  error.value = ''
}

function onCancel() {
  editing.value = null
}

function startDelete(grade: Grade) {
  if (!auth.canEdit()) return
  pendingDelete.value = grade
}

function cancelDelete() {
  pendingDelete.value = null
}

async function confirmDelete() {
  const grade = pendingDelete.value
  if (!grade) return
  saving.value = true
  error.value = ''
  try {
    await api.deleteGradeCatalog(grade.id)
    pendingDelete.value = null
    if (editing.value?.id === grade.id) {
      editing.value = null
    }
    await loadGrades()
  } catch (err) {
    error.value = normalizeError(err)
    pendingDelete.value = null
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadGrades()
  loading.value = false
})

async function toggleActive(grade: Grade) {
  if (!auth.canEdit()) return
  saving.value = true
  error.value = ''
  try {
    await api.updateGradeCatalog(grade.id, { is_active: grade.is_active === false })
    await loadGrades()
    if (editing.value?.id === grade.id) {
      editing.value = grades.value.find((item) => item.id === grade.id) ?? null
    }
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section class="card page">
    <header class="page-header">
      <h2>Справочник грейдов</h2>
      <RouterLink :to="{ name: 'grades' }" class="btn secondary">К грейдам</RouterLink>
    </header>

    <GradeCatalogForm
      v-if="auth.canEdit()"
      :mode="editing ? 'edit' : 'create'"
      :grade="editing"
      @saved="onSaved"
      @cancel="onCancel"
    />
    <p v-if="error" class="error">{{ error }}</p>

    <DataTable
      :columns="columns"
      :rows="grades"
      row-key="id"
      :loading="loading"
      search-placeholder="Поиск по справочнику..."
    >
      <template #cell-is_active="{ row }">
        <span :class="row.is_active === false ? 'badge muted' : 'badge'">
          {{ row.is_active === false ? 'Неактивен' : 'Активен' }}
        </span>
      </template>
      <template #cell-actions="{ row }">
        <div v-if="auth.canEdit()" class="row-actions">
          <button class="btn secondary" type="button" @click="startEdit(row)">Изменить</button>
          <button class="btn ghost" type="button" :disabled="saving" @click="toggleActive(row)">
            {{ row.is_active === false ? 'Активировать' : 'Деактивировать' }}
          </button>
          <button class="btn ghost" type="button" :disabled="saving" @click="startDelete(row)">
            Удалить
          </button>
        </div>
      </template>
    </DataTable>

    <ConfirmDialog
      :open="pendingDelete != null"
      :title="deleteTitle"
      :message="deleteMessage"
      confirm-label="Удалить"
      danger
      @confirm="confirmDelete"
      @cancel="cancelDelete"
    />
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
  gap: 1rem;
}

.row-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.error {
  color: var(--danger);
  margin: 0;
}

.badge.muted {
  opacity: 0.75;
}
</style>
