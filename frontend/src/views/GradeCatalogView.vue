<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import { api } from '@/api/client'
import type { ColumnDef } from '@/composables/useDataTable'
import type { Grade } from '@/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const grades = ref<Grade[]>([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const editing = ref<Grade | null>(null)
const form = ref({
  name: '',
  rank: 1,
  min_years: 1,
})

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

const formTitle = computed(() => (editing.value ? 'Редактировать грейд' : 'Добавить грейд'))

async function loadGrades() {
  grades.value = (await api.gradeCatalog()) as Grade[]
}

function resetForm() {
  const nextRank = grades.value.reduce((max, grade) => Math.max(max, grade.rank), 0) + 1
  form.value = { name: '', rank: nextRank, min_years: 1 }
  editing.value = null
}

function startEdit(grade: Grade) {
  editing.value = grade
  form.value = {
    name: grade.name,
    rank: grade.rank,
    min_years: grade.min_years,
  }
}

onMounted(async () => {
  await loadGrades()
  resetForm()
  loading.value = false
})

async function saveGrade() {
  if (!auth.isAdmin()) return
  saving.value = true
  error.value = ''
  try {
    const body = {
      name: form.value.name.trim(),
      rank: form.value.rank,
      min_years: form.value.min_years,
    }
    if (editing.value) {
      await api.updateGradeCatalog(editing.value.id, body)
    } else {
      await api.createGradeCatalog(body)
    }
    await loadGrades()
    resetForm()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Не удалось сохранить грейд'
  } finally {
    saving.value = false
  }
}

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
    error.value = err instanceof Error ? err.message : 'Не удалось изменить статус'
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

    <form v-if="auth.isAdmin()" class="form" @submit.prevent="saveGrade">
      <h3>{{ formTitle }}</h3>
      <label>
        Название
        <input v-model="form.name" required />
      </label>
      <label>
        Ранг
        <input v-model.number="form.rank" type="number" min="1" step="1" required />
      </label>
      <label>
        Мин. лет до следующего грейда
        <input v-model.number="form.min_years" type="number" min="0.5" step="0.5" required />
      </label>
      <div class="actions">
        <button class="btn" type="submit" :disabled="saving">
          {{ saving ? 'Сохранение...' : editing ? 'Сохранить изменения' : 'Добавить грейд' }}
        </button>
        <button
          v-if="editing"
          class="btn secondary"
          type="button"
          :disabled="saving"
          @click="resetForm"
        >
          Отмена
        </button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </form>

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

.form {
  display: grid;
  gap: 0.75rem;
  max-width: 520px;
}

.form h3 {
  margin: 0;
}

label {
  display: grid;
  gap: 0.35rem;
}

input {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.75rem 0.9rem;
}

.actions,
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
