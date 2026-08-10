<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api } from '@/api/client'
import type { Employee, RewardRow } from '@/types'

const props = defineProps<{
  initial?: RewardRow | null
}>()

const emit = defineEmits<{
  saved: []
  cancel: []
}>()

const form = ref({
  employment_id: '',
  reward_type: '',
  status: 'not_delivered',
  directive_text: '',
  delivered_date: '',
  notes: '',
})
const employees = ref<Employee[]>([])
const submitting = ref(false)
const error = ref('')

watch(
  () => props.initial,
  (value) => {
    if (!value) {
      form.value = {
        employment_id: '',
        reward_type: '',
        status: 'not_delivered',
        directive_text: '',
        delivered_date: '',
        notes: '',
      }
      return
    }

    form.value = {
      employment_id: String(value.employment_id),
      reward_type: value.reward_type,
      status: value.status,
      directive_text: value.directive_text ?? '',
      delivered_date: value.delivered_date ?? '',
      notes: value.notes ?? '',
    }
  },
  { immediate: true },
)

onMounted(async () => {
  const data = await api.employees({ per_page: 200 })
  employees.value = data.items as Employee[]
})

async function submit() {
  submitting.value = true
  error.value = ''
  try {
    const body = {
      employment_id: Number(form.value.employment_id),
      reward_type: form.value.reward_type.trim(),
      status: form.value.status,
      directive_text: form.value.directive_text.trim() || undefined,
      delivered_date: form.value.delivered_date || undefined,
      notes: form.value.notes.trim() || undefined,
    }

    if (props.initial) {
      await api.updateReward(props.initial.id, body)
    } else {
      await api.createReward(body)
    }

    emit('saved')
    if (!props.initial) {
      form.value = {
        employment_id: '',
        reward_type: '',
        status: 'not_delivered',
        directive_text: '',
        delivered_date: '',
        notes: '',
      }
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Не удалось сохранить поощрение'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <form class="form" @submit.prevent="submit">
    <h3>{{ initial ? 'Редактирование поощрения' : 'Новое поощрение' }}</h3>
    <label>
      Сотрудник
      <select v-model="form.employment_id" required>
        <option value="">Выберите сотрудника</option>
        <option v-for="employee in employees" :key="employee.id" :value="String(employee.id)">
          {{ employee.full_name ?? `ID ${employee.id}` }}
        </option>
      </select>
    </label>
    <label>
      Вид поощрения
      <input v-model="form.reward_type" required />
    </label>
    <label>
      Состояние
      <select v-model="form.status">
        <option value="not_delivered">Не вручено</option>
        <option value="in_hr">В кадрах</option>
        <option value="delivered">Вручено</option>
      </select>
    </label>
    <label>
      Указание на вручение
      <textarea v-model="form.directive_text" rows="2" />
    </label>
    <label>
      Дата вручения
      <input v-model="form.delivered_date" type="date" />
    </label>
    <label>
      Примечание
      <textarea v-model="form.notes" rows="3" />
    </label>
    <div class="actions">
      <button class="btn" type="submit" :disabled="submitting">
        {{ submitting ? 'Сохранение...' : 'Сохранить' }}
      </button>
      <button v-if="initial" class="btn ghost" type="button" @click="emit('cancel')">
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
  max-width: 520px;
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
