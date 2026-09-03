<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api } from '@/api/client'
import type { ContractRow } from '@/types'
import { formatShortDate, subtractMonthsFromIsoDate, subtractYearsFromIsoDate } from '@/utils/dates'

const STANDARD_TERMS: readonly string[] = ['1', '2', '3', '5']
const REPORT_LEAD_MONTHS = 4

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
  report_date: '',
})
const submitting = ref(false)
const error = ref('')
const applyingRow = ref(false)
const syncingReport = ref(false)
const reportDateTouched = ref(false)

function defaultReportDate(endDate: string): string {
  if (!endDate) return ''
  return subtractMonthsFromIsoDate(endDate, REPORT_LEAD_MONTHS)
}

function displayedReportDate(row: ContractRow | null): string {
  const event = row?.renewal_report_event
  if (!event) return defaultReportDate(row?.end_date ?? '')
  if (event.status === 'completed' && event.completed_date) {
    return event.completed_date
  }
  return event.event_date
}

function isStandardTerm(value: string): boolean {
  return STANDARD_TERMS.includes(value)
}

function resetForm(row: ContractRow | null) {
  applyingRow.value = true
  reportDateTouched.value = false
  const endDate = row?.end_date ?? ''
  form.value = {
    term_years:
      row?.term_years !== null && row?.term_years !== undefined ? String(row.term_years) : '',
    end_date: endDate,
    report_date: displayedReportDate(row),
  }
  applyingRow.value = false
}

watch(
  () => props.row,
  (row) => resetForm(row),
  { immediate: true },
)

watch(
  () => form.value.end_date,
  (endDate) => {
    if (applyingRow.value || reportDateTouched.value) return
    syncingReport.value = true
    form.value.report_date = defaultReportDate(endDate)
    syncingReport.value = false
  },
  { flush: 'sync' },
)

watch(
  () => form.value.report_date,
  () => {
    if (applyingRow.value || syncingReport.value) return
    reportDateTouched.value = true
  },
  { flush: 'sync' },
)

const derivedStart = computed(() => {
  const endDate = form.value.end_date
  const years = Number(form.value.term_years)
  if (!endDate || !Number.isFinite(years) || years <= 0) {
    return formatShortDate(props.row?.start_date)
  }
  return formatShortDate(subtractYearsFromIsoDate(endDate, years))
})

async function submit() {
  if (!props.row) return
  if (!form.value.term_years || !form.value.end_date) {
    error.value = 'Укажите срок договора и дату окончания'
    return
  }
  if (!form.value.report_date) {
    error.value = 'Укажите дату рапорта'
    return
  }
  submitting.value = true
  error.value = ''
  try {
    await api.updateContract(props.row.id, {
      term_years: Number(form.value.term_years),
      end_date: form.value.end_date,
      report_date: form.value.report_date,
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
        <input v-model="form.end_date" name="end_date" type="date" required />
      </label>
      <label>
        Дата рапорта
        <input v-model="form.report_date" name="report_date" type="date" required />
      </label>
    </div>
    <p class="hint">
      По умолчанию за 4 месяца до окончания, можно указать другую дату.
    </p>

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

.hint {
  margin: 0;
  color: var(--muted);
  font-size: 0.88rem;
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
