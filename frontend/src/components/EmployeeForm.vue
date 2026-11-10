<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import GradeCreateModal from '@/components/GradeCreateModal.vue'
import { api } from '@/api/client'
import type { EducationStatus, Employee, EmployeePeriod, Grade } from '@/types'
import { useAuthStore } from '@/stores/auth'

type GradeField = 'position' | 'actual'
type PeriodDraft = { id: number | null; hire_date: string; dismissal_date: string }

const props = defineProps<{
  initial?: Employee | null
  readonly?: boolean
}>()

const emit = defineEmits<{
  saved: []
  cancel: []
}>()

const auth = useAuthStore()
const form = ref<{
  full_name: string
  title: string
  cardnumber: string
  fio_short: string
  position_short_name: string
  formal_department_short_name: string
  formal_department_name: string
  hire_date: string
  education_status: EducationStatus | ''
  position_grade_id: string
  actual_grade_id: string
  grade_date: string
  contract_term_years: string
  contract_end: string
  passport_until: string
  tenure_10_received_date: string
  tenure_15_received_date: string
  tenure_20_received_date: string
}>({
  full_name: '',
  title: '',
  cardnumber: '',
  fio_short: '',
  position_short_name: '',
  formal_department_short_name: '',
  formal_department_name: '',
  hire_date: '',
  education_status: '',
  position_grade_id: '',
  actual_grade_id: '',
  grade_date: '',
  contract_term_years: '',
  contract_end: '',
  passport_until: '',
  tenure_10_received_date: '',
  tenure_15_received_date: '',
  tenure_20_received_date: '',
})
const grades = ref<Grade[]>([])
const activeGrades = computed(() => grades.value.filter((grade) => grade.is_active !== false))
const submitting = ref(false)
const error = ref('')
const createGradeFor = ref<GradeField | null>(null)
const periods = ref<PeriodDraft[]>([{ id: null, hire_date: '', dismissal_date: '' }])
const periodsLoading = ref(false)
const periodsError = ref('')
let periodsRequestId = 0

function addPeriod() {
  if (props.readonly || periods.value.length >= 3) return
  periods.value.push({ id: null, hire_date: '', dismissal_date: '' })
}

function removePeriod(index: number) {
  if (props.readonly || periods.value.length <= 1 || periods.value[index]?.id !== null) return
  periods.value.splice(index, 1)
}

function validatePeriods() {
  if (periodsLoading.value || periodsError.value) {
    throw new Error('Не удалось загрузить историю работы. Откройте карточку повторно')
  }
  periods.value.forEach((period, index) => {
    const number = index + 1
    if (!period.hire_date) throw new Error('Укажите начало работы периода ' + number)
    if (period.dismissal_date && period.dismissal_date < period.hire_date) {
      throw new Error('Увольнение периода ' + number + ' не может быть раньше начала')
    }
    if (index < periods.value.length - 1 && !period.dismissal_date) {
      throw new Error('Укажите дату увольнения периода ' + number)
    }
    if (index > 0) {
      const previousEnd = periods.value[index - 1]?.dismissal_date
      if (!previousEnd || period.hire_date <= previousEnd) {
        throw new Error('Начало периода ' + number + ' должно быть позже увольнения предыдущего')
      }
    }
  })
}


function resetForm() {
  periods.value = [{ id: null, hire_date: '', dismissal_date: '' }]
  periodsLoading.value = false
  periodsError.value = ''
  form.value = {
    full_name: '',
    title: '',
    cardnumber: '',
    fio_short: '',
    position_short_name: '',
    formal_department_short_name: '',
    formal_department_name: '',
    hire_date: '',
    education_status: '',
    position_grade_id: '',
    actual_grade_id: '',
    grade_date: '',
    contract_term_years: '',
    contract_end: '',
    passport_until: '',
    tenure_10_received_date: '',
    tenure_15_received_date: '',
    tenure_20_received_date: '',
  }
}

watch(
  () => props.initial,
  (value) => {
    const requestId = ++periodsRequestId
    if (!value) {
      resetForm()
      return
    }
    periods.value = [{ id: null, hire_date: value.hire_date, dismissal_date: '' }]
    periodsLoading.value = true
    periodsError.value = ''
    void api.employeePeriods(value.id)
      .then((items: EmployeePeriod[]) => {
        if (requestId !== periodsRequestId) return
        periods.value = items.map((item) => ({
          id: item.id,
          hire_date: item.hire_date,
          dismissal_date: item.dismissal_date ?? '',
        }))
      })
      .catch(() => {
        if (requestId !== periodsRequestId) return
        periodsError.value = 'Не удалось загрузить историю периодов работы'
      })
      .finally(() => {
        if (requestId === periodsRequestId) periodsLoading.value = false
      })
    form.value = {
      full_name: value.full_name ?? '',
      title: value.title ?? '',
      cardnumber: value.cardnumber ?? '',
      fio_short: value.fio_short ?? '',
      position_short_name: value.position_short_name ?? '',
      formal_department_short_name: value.formal_department_short_name ?? '',
      formal_department_name: value.formal_department_name ?? '',
      hire_date: value.hire_date ?? '',
      education_status:
        value.education_status === 'unknown' ? '' : value.education_status,
      position_grade_id: value.position_grade ? String(value.position_grade.id) : '',
      actual_grade_id: value.actual_grade ? String(value.actual_grade.id) : '',
      grade_date: value.grade_date ?? '',
      contract_term_years:
        value.contract_term_years !== null && value.contract_term_years !== undefined
          ? String(value.contract_term_years)
          : '',
      contract_end: value.contract_end ?? '',
      passport_until: value.passport_until ?? '',
      tenure_10_received_date: '',
      tenure_15_received_date: '',
      tenure_20_received_date: '',
    }
  },
  { immediate: true },
)

function validateContractFields() {
  const hasEnd = Boolean(form.value.contract_end)
  const hasTerm = Boolean(form.value.contract_term_years)
  if (hasEnd !== hasTerm) {
    throw new Error('Укажите срок договора и дату окончания')
  }
}

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
  if (props.readonly) return
  submitting.value = true
  error.value = ''
  try {
    if (form.value.actual_grade_id && !form.value.grade_date) {
      throw new Error('Укажите дату текущего грейда')
    }
    if (!form.value.education_status) {
      throw new Error('Укажите наличие высшего образования')
    }
    validateContractFields()
    validatePeriods()

    const body: Record<string, unknown> = {
      full_name: form.value.full_name.trim(),
      title: form.value.title.trim() || 'Не указана',
      cardnumber: form.value.cardnumber.trim() || null,
      fio_short: form.value.fio_short.trim() || null,
      position_short_name: form.value.position_short_name.trim() || null,
      formal_department_short_name: form.value.formal_department_short_name.trim() || null,
      formal_department_name: form.value.formal_department_name.trim() || null,
      hire_date: periods.value[periods.value.length - 1]!.hire_date,
      periods: periods.value.map((period) => ({
        id: period.id,
        hire_date: period.hire_date,
        dismissal_date: period.dismissal_date || null,
      })),
      education_status: form.value.education_status,
      position_grade_id: form.value.position_grade_id
        ? Number(form.value.position_grade_id)
        : null,
      actual_grade_id: form.value.actual_grade_id
        ? Number(form.value.actual_grade_id)
        : null,
      grade_date: form.value.grade_date || null,
      contract_term_years: form.value.contract_term_years
        ? Number(form.value.contract_term_years)
        : null,
      contract_end: form.value.contract_end || null,
      passport_until: form.value.passport_until || null,
    }

    if (props.initial) {
      await api.updateEmployee(props.initial.id, body)
    } else {
      body.tenure_10_received_date = form.value.tenure_10_received_date || null
      body.tenure_15_received_date = form.value.tenure_15_received_date || null
      body.tenure_20_received_date = form.value.tenure_20_received_date || null
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
    <h3>{{ initial ? (readonly ? 'Карточка сотрудника' : 'Редактирование сотрудника') : 'Новый сотрудник' }}</h3>
    <div class="grid">
      <label>
        ФИО
        <input v-model="form.full_name" required :disabled="readonly" />
      </label>
      <label>
        Должность
        <input v-model="form.title" name="title" maxlength="256" :disabled="readonly" />
      </label>
      <label>
        Номер карточки
        <input v-model="form.cardnumber" name="cardnumber" maxlength="128" :disabled="readonly" />
      </label>
      <label>
        Сокращённое ФИО
        <input v-model="form.fio_short" name="fio_short" maxlength="256" :disabled="readonly" />
      </label>
      <label>
        Должность сокращённо
        <input v-model="form.position_short_name" name="position_short_name" maxlength="256" :disabled="readonly" />
      </label>
      <label>
        Отдел сокращённо
        <input v-model="form.formal_department_short_name" name="formal_department_short_name" maxlength="256" :disabled="readonly" />
      </label>
      <label>
        Отдел полностью
        <input v-model="form.formal_department_name" name="formal_department_name" :disabled="readonly" />
      </label>
      <p class="directory-note">При включённой синхронизации внешний сервис обновляет номер карточки, сокращённое ФИО, должность и формальный отдел. Грейды ведутся в BookHR.</p>
      <section class="periods-section" aria-label="Периоды работы">
        <div class="periods-heading">
          <div>
            <h4>Периоды работы</h4>
            <p>Учитываются при расчёте суммарного стажа и наград за выслугу лет.</p>
          </div>
          <button
            v-if="!readonly && periods.length < 3"
            class="btn ghost period-add"
            type="button"
            :disabled="periodsLoading || Boolean(periodsError)"
            @click="addPeriod"
          >+ Добавить период</button>
        </div>
        <p v-if="periodsLoading" class="period-hint">Загрузка истории работы…</p>
        <p v-if="periodsError" class="error" role="alert">{{ periodsError }}</p>
        <div class="periods-list">
          <div v-for="(period, index) in periods" :key="period.id ?? 'new-' + index" class="period-card">
            <div class="period-card-header">
              <strong>Период {{ index + 1 }}</strong>
              <span v-if="index === periods.length - 1 && !period.dismissal_date" class="period-current">Текущий</span>
              <span v-else-if="period.dismissal_date" class="period-closed">Завершён</span>
              <button
                v-if="!readonly && period.id === null && periods.length > 1"
                class="btn ghost period-remove"
                type="button"
                :disabled="periodsLoading"
                @click="removePeriod(index)"
              >Убрать</button>
            </div>
            <div class="period-fields">
              <label>
                Начало работы
                <input v-model="period.hire_date" name="period_hire_date" type="date" required :disabled="readonly || periodsLoading || Boolean(periodsError)" />
              </label>
              <label>
                Дата увольнения
                <input v-model="period.dismissal_date" name="period_dismissal_date" type="date" :disabled="readonly || periodsLoading || Boolean(periodsError)" />
              </label>
            </div>
          </div>
        </div>
        <p class="period-hint">До 3 периодов. Перед следующим приёмом укажите дату увольнения. Для работающего сотрудника последнее увольнение оставьте пустым. Сохранённые периоды нельзя убрать из карточки — только исправить даты.</p>
      </section>
      <label>
        Высшее образование
        <select v-model="form.education_status" required :disabled="readonly">
          <option value="" disabled>Выберите значение</option>
          <option value="yes">Есть</option>
          <option value="no">Нет</option>
        </select>
      </label>
      <div class="field-with-action">
        <label>
          Грейд по должности
          <select v-model="form.position_grade_id" :disabled="readonly">
            <option value="">Не указан</option>
            <option v-for="grade in activeGrades" :key="grade.id" :value="String(grade.id)">
              {{ grade.name }}
            </option>
          </select>
        </label>
        <button
          v-if="auth.canEdit() && !readonly"
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
          <select v-model="form.actual_grade_id" :disabled="readonly">
            <option value="">Не указан</option>
            <option v-for="grade in activeGrades" :key="grade.id" :value="String(grade.id)">
              {{ grade.name }}
            </option>
          </select>
        </label>
        <button
          v-if="auth.canEdit() && !readonly"
          class="btn ghost"
          type="button"
          @click="openGradeModal('actual')"
        >
          + Новый грейд
        </button>
      </div>
      <label>
        Дата текущего грейда
        <input
          v-model="form.grade_date"
          type="date"
          :required="Boolean(form.actual_grade_id)"
          :disabled="readonly"
        />
      </label>
      <label>
        Срок договора (лет)
        <select v-model="form.contract_term_years" :disabled="readonly">
          <option value="">Не указан</option>
          <option value="1">1 год</option>
          <option value="2">2 года</option>
          <option value="3">3 года</option>
          <option value="5">5 лет</option>
          <option
            v-if="
              form.contract_term_years &&
              !['1', '2', '3', '5'].includes(form.contract_term_years)
            "
            :value="form.contract_term_years"
          >
            {{ form.contract_term_years }} г.
          </option>
        </select>
      </label>
      <label>
        Окончание договора
        <input v-model="form.contract_end" name="contract_end" type="date" :disabled="readonly" />
      </label>
      <label>
        Срок паспорта
        <input v-model="form.passport_until" type="date" :disabled="readonly" />
      </label>
      <template v-if="!initial">
        <div class="section-title">Награды за стаж</div>
        <label>
          Дата получения награды за 10 лет
          <input v-model="form.tenure_10_received_date" type="date" :disabled="readonly" />
        </label>
        <label>
          Дата получения награды за 15 лет
          <input v-model="form.tenure_15_received_date" type="date" :disabled="readonly" />
        </label>
        <label>
          Дата получения награды за 20 лет
          <input v-model="form.tenure_20_received_date" type="date" :disabled="readonly" />
        </label>
      </template>
    </div>
    <div v-if="!readonly" class="actions">
      <button class="btn" type="submit" :disabled="submitting || periodsLoading || Boolean(periodsError)">
        {{ submitting ? 'Сохранение...' : 'Сохранить' }}
      </button>
      <button class="btn ghost" type="button" @click="emit('cancel')">
        Отмена
      </button>
    </div>
    <div v-else class="actions">
      <button class="btn ghost" type="button" @click="emit('cancel')">
        Закрыть
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
.periods-section { grid-column: 1 / -1; display: grid; gap: 0.75rem; min-width: 0; }
.periods-heading { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.65rem; }
.periods-heading h4 { margin: 0 0 0.25rem; font-size: 1rem; }
.periods-heading p, .period-hint { margin: 0; font-size: 0.85rem; color: var(--muted); }
.periods-list { display: grid; gap: 0.65rem; }
.period-card { border: 1px solid var(--border); border-radius: var(--radius-md); padding: 0.85rem; display: grid; gap: 0.7rem; }
.period-card-header { display: flex; align-items: center; gap: 0.55rem; flex-wrap: wrap; }
.period-card-header strong { font-size: 0.92rem; }
.period-current, .period-closed { font-size: 0.78rem; color: var(--muted); }
.period-current { color: var(--success, #15803d); }
.period-remove { margin-left: auto; color: var(--danger); }
.period-fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.7rem; }
.period-add { flex-shrink: 0; }
.directory-note { grid-column: 1 / -1; color: var(--muted); font-size: 0.85rem; margin: 0; }

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

.section-title {
  grid-column: 1 / -1;
  font-weight: 600;
  margin-top: 0.25rem;
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
