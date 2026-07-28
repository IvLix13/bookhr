<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api } from '@/api/client'
import type { Employee, Paginated } from '@/types'

const props = defineProps<{
  initialDate: string
  compact?: boolean
}>()

const emit = defineEmits<{
  created: []
  cancel: []
}>()

const form = ref({
  title: '',
  event_type: 'manual',
  event_date: props.initialDate,
  description: '',
  employment_id: '',
})
const employees = ref<Employee[]>([])
const submitting = ref(false)
const error = ref('')

watch(
  () => props.initialDate,
  (value) => {
    form.value.event_date = value
  },
)

onMounted(async () => {
  const data = (await api.employees('?per_page=200')) as Paginated<Employee>
  employees.value = data.items
})

async function submit() {
  submitting.value = true
  error.value = ''
  try {
    await api.createEvent({
      title: form.value.title,
      event_type: form.value.event_type,
      event_date: form.value.event_date,
      description: form.value.description || undefined,
      employment_id: form.value.employment_id ? Number(form.value.employment_id) : undefined,
    })
    form.value.title = ''
    form.value.description = ''
    emit('created')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Не удалось создать мероприятие'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <form class="form" :class="{ compact }" @submit.prevent="submit">
    <label>
      Название
      <input v-model="form.title" required />
    </label>
    <label>
      Тип
      <select v-model="form.event_type">
        <option value="contract">Договор</option>
        <option value="grade">Грейд</option>
        <option value="award">Поощрение</option>
        <option value="report">Рапорт</option>
        <option value="passport">Паспорт</option>
        <option value="manual">Другое</option>
      </select>
    </label>
    <label>
      Дата
      <input v-model="form.event_date" type="date" required />
    </label>
    <label>
      Сотрудник
      <select v-model="form.employment_id">
        <option value="">Без привязки</option>
        <option v-for="employee in employees" :key="employee.id" :value="String(employee.id)">
          {{ employee.full_name ?? `ID ${employee.id}` }}
        </option>
      </select>
    </label>
    <label>
      Описание
      <textarea v-model="form.description" :rows="compact ? 3 : 4" />
    </label>
    <div class="actions">
      <button class="btn" type="submit" :disabled="submitting">
        {{ submitting ? 'Сохранение...' : 'Сохранить' }}
      </button>
      <button v-if="compact" class="btn ghost" type="button" @click="emit('cancel')">Отмена</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
  </form>
</template>

<style scoped>
.form {
  display: grid;
  gap: 0.85rem;
  max-width: 520px;
}

.form.compact {
  max-width: none;
}

label {
  display: grid;
  gap: 0.35rem;
}

input,
select,
textarea {
  border: 1px solid var(--border);
  border-radius: 10px;
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
