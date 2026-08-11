<script setup lang="ts">
import { onMounted, ref } from 'vue'
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
const form = ref({
  name: '',
  rank: 1,
  min_months: 12,
})

const columns: ColumnDef<Grade>[] = [
  { key: 'name', label: 'Название' },
  { key: 'rank', label: 'Ранг' },
  { key: 'min_months', label: 'Мин. месяцев' },
]

async function loadGrades() {
  grades.value = (await api.gradeCatalog()) as Grade[]
}

onMounted(async () => {
  await loadGrades()
  loading.value = false
})

async function createGrade() {
  if (!auth.isAdmin()) return
  saving.value = true
  error.value = ''
  try {
    await api.createGradeCatalog({
      name: form.value.name.trim(),
      rank: form.value.rank,
      min_months: form.value.min_months,
    })
    form.value = { name: '', rank: form.value.rank + 1, min_months: 12 }
    await loadGrades()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Не удалось создать грейдов'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section class="card page">
    <header class="page-header">
      <h2>Справочник грейдов</h2>
      <RouterLink :to="{ name: 'grades' }" class="btn secondary">К грейдым</RouterLink>
    </header>

    <form v-if="auth.isAdmin()" class="form" @submit.prevent="createGrade">
      <label>
        Название
        <input v-model="form.name" required />
      </label>
      <label>
        Ранг
        <input v-model.number="form.rank" type="number" min="1" required />
      </label>
      <label>
        Мин. месяцев
        <input v-model.number="form.min_months" type="number" min="0" required />
      </label>
      <button class="btn" type="submit" :disabled="saving">
        {{ saving ? 'Сохранение...' : 'Добавить грейдов' }}
      </button>
      <p v-if="error" class="error">{{ error }}</p>
    </form>

    <DataTable
      :columns="columns"
      :rows="grades"
      row-key="id"
      :loading="loading"
      search-placeholder="Поиск по справочнику..."
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

.form {
  display: grid;
  gap: 0.75rem;
  max-width: 520px;
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

.error {
  color: var(--danger);
  margin: 0;
}
</style>
