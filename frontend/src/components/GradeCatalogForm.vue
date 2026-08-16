<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import type { Grade } from '@/types'

const props = withDefaults(
  defineProps<{
    mode?: 'create' | 'edit'
    grade?: Grade | null
    initialName?: string
  }>(),
  {
    mode: 'create',
    grade: null,
    initialName: '',
  },
)

const emit = defineEmits<{
  saved: [grade: Grade]
  cancel: []
}>()

const grades = ref<Grade[]>([])
const saving = ref(false)
const error = ref('')
const form = ref({
  name: '',
  rank: 1,
  min_years: 1,
  extra_year_without_university: false,
})

const formTitle = computed(() =>
  props.mode === 'edit' ? 'Редактировать грейд' : 'Добавить грейд',
)

const submitLabel = computed(() => {
  if (saving.value) return 'Сохранение...'
  return props.mode === 'edit' ? 'Сохранить изменения' : 'Добавить грейд'
})

async function loadGrades() {
  grades.value = (await api.gradeCatalog()) as Grade[]
}

function nextRank(): number {
  return grades.value.reduce((max, grade) => Math.max(max, grade.rank), 0) + 1
}

function applyFormFromProps() {
  switch (props.mode) {
    case 'edit': {
      if (props.grade) {
        form.value = {
          name: props.grade.name,
          rank: props.grade.rank,
          min_years: props.grade.min_years,
          extra_year_without_university:
            props.grade.extra_year_without_university,
        }
        return
      }
      break
    }
    case 'create':
      break
    default: {
      const _exhaustive: never = props.mode
      return _exhaustive
    }
  }
  form.value = {
    name: props.initialName.trim(),
    rank: nextRank(),
    min_years: 1,
    extra_year_without_university: false,
  }
}

onMounted(async () => {
  await loadGrades()
  applyFormFromProps()
})

watch(
  () => [props.mode, props.grade?.id, props.initialName] as const,
  () => {
    applyFormFromProps()
  },
)

async function saveGrade() {
  saving.value = true
  error.value = ''
  try {
    const body = {
      name: form.value.name.trim(),
      rank: form.value.rank,
      min_years: form.value.min_years,
      extra_year_without_university: form.value.extra_year_without_university,
    }
    let saved: Grade
    switch (props.mode) {
      case 'edit': {
        if (!props.grade) {
          throw new Error('Не выбран грейд для редактирования')
        }
        saved = (await api.updateGradeCatalog(props.grade.id, body)) as Grade
        break
      }
      case 'create':
        saved = (await api.createGradeCatalog(body)) as Grade
        break
      default: {
        const _exhaustive: never = props.mode
        return _exhaustive
      }
    }
    await loadGrades()
    emit('saved', saved)
    if (props.mode === 'create') {
      applyFormFromProps()
    }
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    saving.value = false
  }
}

function cancel() {
  applyFormFromProps()
  emit('cancel')
}
</script>

<template>
  <form class="form" @submit.prevent="saveGrade">
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
    <label class="checkbox">
      <input v-model="form.extra_year_without_university" type="checkbox" />
      Добавлять один год сотрудникам без ВУЗа
    </label>
    <div class="actions">
      <button class="btn" type="submit" :disabled="saving">
        {{ submitLabel }}
      </button>
      <button class="btn secondary" type="button" :disabled="saving" @click="cancel">
        Отмена
      </button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
  </form>
</template>

<style scoped>
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

label.checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

input {
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
