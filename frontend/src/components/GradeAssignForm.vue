<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '@/api/client'
import type { Grade, GradeRow } from '@/types'

const props = defineProps<{
  initial?: GradeRow | null
}>()

const emit = defineEmits<{
  saved: []
  cancel: []
}>()

const form = ref({
  grade_id: '',
  assigned_date: '',
  basis: '',
})
const grades = ref<Grade[]>([])
const submitting = ref(false)
const error = ref('')

const activeGrades = computed(() => grades.value.filter((grade) => grade.is_active !== false))

watch(
  () => props.initial,
  (value) => {
    if (!value) {
      form.value = { grade_id: '', assigned_date: '', basis: '' }
      return
    }
    form.value = {
      grade_id: value.grade?.id ? String(value.grade.id) : '',
      assigned_date: value.grade_date ?? '',
      basis: '',
    }
  },
  { immediate: true },
)

onMounted(async () => {
  grades.value = (await api.gradeCatalog()) as Grade[]
})

async function submit() {
  if (!props.initial) return
  if (!form.value.grade_id || !form.value.assigned_date) {
    error.value = 'Выберите грейд и укажите дату назначения'
    return
  }

  submitting.value = true
  error.value = ''
  try {
    await api.assignGrade({
      employment_id: props.initial.employment_id,
      grade_id: Number(form.value.grade_id),
      assigned_date: form.value.assigned_date,
      basis: form.value.basis.trim() || undefined,
    })
    emit('saved')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Не удалось назначить грейд'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <form v-if="initial" class="form card" @submit.prevent="submit">
    <header class="form-header">
      <h3>{{ initial.grade ? 'Изменить грейд' : 'Назначить грейд' }}</h3>
      <p>{{ initial.full_name }}</p>
    </header>

    <label>
      Грейд
      <select v-model="form.grade_id" required>
        <option value="" disabled>Выберите грейд</option>
        <option v-for="grade in activeGrades" :key="grade.id" :value="String(grade.id)">
          {{ grade.name }} (ранг {{ grade.rank }}, {{ grade.min_years }} г.)
        </option>
      </select>
    </label>

    <label>
      Дата назначения
      <input v-model="form.assigned_date" type="date" required />
    </label>

    <label>
      Основание
      <textarea v-model="form.basis" rows="2" placeholder="Необязательно" />
    </label>

    <div class="actions">
      <button class="btn" type="submit" :disabled="submitting">
        {{ submitting ? 'Сохранение...' : 'Сохранить' }}
      </button>
      <button class="btn secondary" type="button" @click="emit('cancel')">Отмена</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
  </form>
</template>

<style scoped>
.form {
  padding: 1rem;
  display: grid;
  gap: 0.75rem;
}

.form-header h3 {
  margin: 0;
}

.form-header p {
  margin: 0.35rem 0 0;
  color: var(--muted);
}

label {
  display: grid;
  gap: 0.35rem;
}

input,
select,
textarea {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.75rem 0.9rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.error {
  color: var(--danger);
  margin: 0;
}
</style>
