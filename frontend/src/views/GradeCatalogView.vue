<script setup lang="ts">
import { onMounted, ref } from 'vue'
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

onMounted(async () => {
  await loadGrades()
  loading.value = false
})

async function toggleActive(grade: Grade) {
  if (!auth.isAdmin()) return
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
      v-if="auth.isAdmin()"
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
        <div v-if="auth.isAdmin()" class="row-actions">
          <button class="btn secondary" type="button" @click="startEdit(row)">Изменить</button>
          <button class="btn ghost" type="button" :disabled="saving" @click="toggleActive(row)">
            {{ row.is_active === false ? 'Активировать' : 'Деактивировать' }}
          </button>
        </div>
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
