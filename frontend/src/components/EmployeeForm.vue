<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import GradeCreateModal from '@/components/GradeCreateModal.vue'
import { api } from '@/api/client'
import type { Employee, Grade } from '@/types'
import { useAuthStore } from '@/stores/auth'

type GradeField = 'position' | 'actual'

const props = defineProps<{
  initial?: Employee | null
}>()

const emit = defineEmits<{
  saved: []
  cancel: []
}>()

const auth = useAuthStore()
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
const activeGrades = computed(() => grades.value.filter((grade) => grade.is_active !== false))
const submitting = ref(false)
const error = ref('')
const createGradeFor = ref<GradeField | null>(null)

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

async function loadGrades() {
  grades.value = (await api.gradeCatalog()) as Grade[]
}

onMounted(async () => {
  await loadGrades()
})

function openGradeModal(field: GradeField) {
  createGradeFor.value = field
}

function closeGradeModal() {
  createGradeFor.value = null
}

async function onGradeCreated(grade: Grade) {
  const field = createGradeFor.value
  closeGradeModal()
  await loadGrades()
  switch (field) {
    case 'position':
      form.value.position_grade_id = String(grade.id)
      break
    case 'actual':
      form.value.actual_grade_id = String(grade.id)
      break
    case null:
      break
    default: {
      const _exhaustive: never = field
      return _exhaustive
    }
  }
}

async function submit() {
  submitting.value = true
  error.value = ''
  try {
    if (form.value.actual_grade_id && !form.value.grade_date) {
      throw new Error('Укажите дату текущего грейда')
    }

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
      <div class="field-with-action">
        <label>
          Грейд по должности
          <select v-model="form.position_grade_id">
            <option value="">Не указан</option>
            <option v-for="grade in activeGrades" :key="grade.id" :value="String(grade.id)">
              {{ grade.name }}
            </option>
          </select>
        </label>
        <button
          v-if="auth.isAdmin()"
          class="btn ghost"
          type="button"
          @click="openGradeModal('position')"
        >
          + Новый грейд
        </button>
      </div>
      <div class="field-with-action">
        <label>
          Фактический грейд
          <select v-model="form.actual_grade_id">
            <option value="">Не указан</option>
            <option v-for="grade in activeGrades" :key="grade.id" :value="String(grade.id)">
              {{ grade.name }}
            </option>
          </select>
        </label>
        <button
          v-if="auth.isAdmin()"
          class="btn ghost"
          type="button"
          @click="openGradeModal('actual')"
        >
          + Новый грейд
        </button>
      </div>
      <label>
        Дата текущего грейда
        <input v-model="form.grade_date" type="date" :required="Boolean(form.actual_grade_id)" />
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
    <GradeCreateModal
      :open="createGradeFor !== null"
      @close="closeGradeModal"
      @saved="onGradeCreated"
    />
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

.field-with-action {
  display: grid;
  gap: 0.35rem;
  align-content: start;
}

.field-with-action .btn {
  justify-self: start;
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
