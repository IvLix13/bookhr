<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api } from '@/api/client'
import type { Employee, Grade } from '@/types'

const props = defineProps<{
  initial?: Employee | null
}>()

const emit = defineEmits<{
  saved: []
  cancel: []
}>()

const form = ref({
  full_name: '',
  title: '',
  hire_date: '',
  has_university: false,
  position_grade_id: '',
  actual_grade_id: '',
  grade_date: '',
  contract_end: '',
  passport_until: '',
})
const grades = ref<Grade[]>([])
const submitting = ref(false)
const error = ref('')

function resetForm() {
  form.value = {
    full_name: '',
    title: '',
    hire_date: '',
    has_university: false,
    position_grade_id: '',
    actual_grade_id: '',
    grade_date: '',
    contract_end: '',
    passport_until: '',
  }
}

watch(
  () => props.initial,
  (value) => {
    if (!value) {
      resetForm()
      return
    }
    form.value = {
      full_name: value.full_name ?? '',
      title: value.title ?? '',
      hire_date: value.hire_date ?? '',
      has_university: value.has_university,
      position_grade_id: value.position_grade ? String(value.position_grade.id) : '',
      actual_grade_id: value.actual_grade ? String(value.actual_grade.id) : '',
      grade_date: value.grade_date ?? '',
      contract_end: value.contract_end ?? '',
      passport_until: value.passport_until ?? '',
    }
  },
  { immediate: true },
)

onMounted(async () => {
  grades.value = (await api.gradeCatalog()) as Grade[]
})

async function submit() {
  submitting.value = true
  error.value = ''
  try {
    const body = {
      full_name: form.value.full_name.trim(),
      title: form.value.title.trim() || 'Не указана',
      hire_date: form.value.hire_date,
      has_university: form.value.has_university,
      position_grade_id: form.value.position_grade_id
        ? Number(form.value.position_grade_id)
        : null,
      actual_grade_id: form.value.actual_grade_id
        ? Number(form.value.actual_grade_id)
        : null,
      grade_date: form.value.grade_date || null,
      contract_end: form.value.contract_end || null,
      passport_until: form.value.passport_until || null,
    }

    if (props.initial) {
      await api.updateEmployee(props.initial.id, body)
    } else {
      await api.createEmployee(body)
      resetForm()
    }
    emit('saved')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Не удалось сохранить сотрудника'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <form class="form" @submit.prevent="submit">
    <h3>{{ initial ? 'Редактирование сотрудника' : 'Новый сотрудник' }}</h3>
    <div class="grid">
      <label>
        ФИО
        <input v-model="form.full_name" required />
      </label>
      <label>
        Должность
        <input v-model="form.title" />
      </label>
      <label>
        Начало работы
        <input v-model="form.hire_date" type="date" required />
      </label>
      <label class="checkbox">
        <input v-model="form.has_university" type="checkbox" />
        Есть ВУЗ
      </label>
      <label>
        Грейд по должности
        <select v-model="form.position_grade_id">
          <option value="">Не указан</option>
          <option v-for="grade in grades" :key="grade.id" :value="String(grade.id)">
            {{ grade.name }}
          </option>
        </select>
      </label>
      <label>
        Фактический грейд
        <select v-model="form.actual_grade_id">
          <option value="">Не указан</option>
          <option v-for="grade in grades" :key="grade.id" :value="String(grade.id)">
            {{ grade.name }}
          </option>
        </select>
      </label>
      <label>
        Дата текущего грейда
        <input v-model="form.grade_date" type="date" />
      </label>
      <label>
        Окончание договора
        <input v-model="form.contract_end" type="date" />
      </label>
      <label>
        Срок паспорта
        <input v-model="form.passport_until" type="date" />
      </label>
    </div>
    <div class="actions">
      <button class="btn" type="submit" :disabled="submitting">
        {{ submitting ? 'Сохранение...' : 'Сохранить' }}
      </button>
      <button class="btn ghost" type="button" @click="emit('cancel')">
        Отмена
      </button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
  </form>
</template>

<style scoped>
.form {
  display: grid;
  gap: 0.85rem;
}

.grid {
  display: grid;
  gap: 0.85rem;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

label {
  display: grid;
  gap: 0.35rem;
}

label.checkbox {
  align-content: end;
  grid-auto-flow: column;
  justify-content: start;
  align-items: center;
  gap: 0.5rem;
}

input,
select {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.75rem 0.9rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
}

.error {
  margin: 0;
  color: var(--danger);
}
</style>
