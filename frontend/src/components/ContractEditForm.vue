<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api } from '@/api/client'
import type { ContractRow } from '@/types'
import { formatShortDate, subtractYearsFromIsoDate } from '@/utils/dates'

const STANDARD_TERMS: readonly string[] = ['1', '2', '3', '5']

const props = defineProps<{
  row: ContractRow | null
}>()

const emit = defineEmits<{
  saved: []
  cancel: []
}>()

const form = ref({
  term_years: '',
  end_date: '',
})
const submitting = ref(false)
const error = ref('')

function resetForm(row: ContractRow | null) {
  form.value = {
    term_years:
      row?.term_years !== null && row?.term_years !== undefined ? String(row.term_years) : '',
    end_date: row?.end_date ?? '',
  }
}

watch(
  () => props.row,
  (row) => resetForm(row),
  { immediate: true },
)

const derivedStart = computed(() => {
  const endDate = form.value.end_date
  const years = Number(form.value.term_years)
  if (!endDate || !Number.isFinite(years) || years <= 0) {
    return formatShortDate(props.row?.start_date)
  }
  return formatShortDate(subtractYearsFromIsoDate(endDate, years))
})

function isStandardTerm(value: string): boolean {
  return STANDARD_TERMS.includes(value)
}

async function submit() {
  if (!props.row) return
  if (!form.value.term_years || !form.value.end_date) {
    error.value = 'Укажите срок договора и дату окончания'
    return
  }
  submitting.value = true
  error.value = ''
  try {
    await api.updateContract(props.row.id, {
      term_years: Number(form.value.term_years),
      end_date: form.value.end_date,
    })
    emit('saved')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Не удалось сохранить договор'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <form v-if="row" class="form card" @submit.prevent="submit">
    <header class="form-header">
      <div>
        <h3>Редактирование договора: {{ row.full_name ?? 'Сотрудник' }}</h3>
        <p>
          Дата начала считается автоматически от срока и даты окончания:
          {{ derivedStart }}
        </p>
      </div>
      <button class="btn ghost" type="button" @click="emit('cancel')">×</button>
    </header>

    <div class="fields">
      <label>
        Срок договора (лет)
        <select v-model="form.term_years" required>
          <option value="" disabled>Выберите срок</option>
          <option value="1">1 год</option>
          <option value="2">2 года</option>
          <option value="3">3 года</option>
          <option value="5">5 лет</option>
          <option
            v-if="form.term_years && !isStandardTerm(form.term_years)"
            :value="form.term_years"
          >
            {{ form.term_years }} г.
          </option>
        </select>
      </label>
      <label>
        Окончание договора
        <input v-model="form.end_date" type="date" required />
      </label>
    </div>

    <div class="actions">
      <button class="btn" type="submit" :disabled="submitting">
        {{ submitting ? 'Сохранение...' : 'Сохранить' }}
      </button>
      <button class="btn ghost" type="button" @click="emit('cancel')">Отмена</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
  </form>
</template>

<style scoped>
.form {
  padding: 1rem;
  display: grid;
  gap: 1rem;
}

.form-header {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 1rem;
}

.form-header h3 {
  margin: 0;
}

.form-header p {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.92rem;
}

.fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

label {
  display: grid;
  gap: 0.35rem;
}

select,
input[type='date'] {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.65rem 0.75rem;
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
