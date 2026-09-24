<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import { formatShortDate } from '@/utils/dates'
import OnboardingCellEditor from '@/components/OnboardingCellEditor.vue'
import OnboardingColumnsModal from '@/components/OnboardingColumnsModal.vue'
import type { Employee, Paginated } from '@/types'
import type { OnboardingCell, OnboardingColumn, OnboardingPlan } from '@/types/onboarding'

const auth = useAuthStore()
const columns = ref<OnboardingColumn[]>([])
const visibleColumns = computed(() => columns.value.filter(c => !c.is_archived))
const plans = ref<OnboardingPlan[]>([])
const page = ref(1)
const pages = ref(0)
const total = ref(0)
const query = ref('')
const loading = ref(false)
const error = ref('')
const showColumns = ref(false)
const showAdd = ref(false)
const employeeQuery = ref('')
const employeePage = ref(1)
const employeePages = ref(0)
const employees = ref<Employee[]>([])
const finding = ref(false)
const adding = ref(false)
const addError = ref('')
const exporting = ref(false)
const exportError = ref('')
const editing = ref<{ planId: number; employeeName: string; column: OnboardingColumn; cell?: OnboardingCell } | null>(null)
let requestId = 0
let employeeRequestId = 0
async function load() {
  const id = ++requestId
  loading.value = true
  error.value = ''
  try {
    const [structure, data] = await Promise.all([api.onboardingColumns(), api.onboardingPlans({ page: page.value, per_page: 25, q: query.value })])
    if (id !== requestId) return
    columns.value = structure
    plans.value = data.items
    total.value = data.total
    pages.value = data.pages
  } catch (err) { if (id === requestId) error.value = normalizeError(err) }
  finally { if (id === requestId) loading.value = false }
}
function search() { page.value = 1; void load() }
function changePage(delta: number) { page.value += delta; void load() }
async function findEmployees(reset = false) {
  if (reset) employeePage.value = 1
  const id = ++employeeRequestId
  finding.value = true
  addError.value = ''
  try {
    const data = await api.employees({ q: employeeQuery.value, active_only: false, page: employeePage.value, per_page: 15 }) as Paginated<Employee>
    if (id !== employeeRequestId) return
    employees.value = data.items
    employeePages.value = data.pages
  } catch (err) { if (id === employeeRequestId) addError.value = normalizeError(err) }
  finally { if (id === employeeRequestId) finding.value = false }
}
function openAdd() { showAdd.value = !showAdd.value; if (showAdd.value) void findEmployees(true) }
async function add(employee: Employee) {
  adding.value = true
  addError.value = ''
  try {
    await api.createOnboardingPlan(employee.id)
    showAdd.value = false
    query.value = ''
    page.value = 1
    await load()
    if (pages.value > 1) { page.value = pages.value; await load() }
  } catch (err) { addError.value = normalizeError(err) }
  finally { adding.value = false }
}
async function downloadExcel() {
  exporting.value = true
  exportError.value = ''
  try {
    await api.downloadOnboarding()
  } catch (err) {
    exportError.value = normalizeError(err)
  } finally {
    exporting.value = false
  }
}
function startEdit(plan: OnboardingPlan, column: OnboardingColumn) {
  if (!auth.canEdit()) return
  editing.value = { planId: plan.id, employeeName: plan.full_name ?? 'Сотрудник', column: { ...column }, cell: plan.cells[column.id] ? { ...plan.cells[column.id]! } : undefined }
}
function cellLabel(plan: OnboardingPlan, column: OnboardingColumn) {
  const cell = plan.cells[column.id]
  if (cell?.is_not_required) return 'Не нужно'
  if (column.field_type === 'checkbox') return cell?.is_completed ? '✓' : '□ Не выполнено'
  if (!cell) return '—'
  if (column.field_type === 'text') return cell.text_value || '—'
  if (column.field_type === 'date') return formatShortDate(cell.date_value)
  return cell.is_completed ? `✓ ${formatShortDate(cell.completed_date)}` : formatShortDate(cell.planned_date)
}
function overdue(column: OnboardingColumn, cell?: OnboardingCell) {
  const today = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Moscow' }).format(new Date())
  return column.field_type === 'stage' && !!cell?.planned_date && !cell.is_completed && !cell.is_not_required && cell.planned_date < today
}
function saved() { editing.value = null; void load() }
onMounted(load)
</script>

<template>
  <section class="card onboarding-page">
    <header><h2>План обучения</h2><p>Ввод сотрудников в должность</p></header>
    <div class="toolbar">
      <form @submit.prevent="search"><input v-model="query" aria-label="Поиск планов по ФИО" placeholder="ФИО (от 2 символов)" /><button class="btn" :disabled="loading">Найти</button></form>
      <button v-if="auth.canEdit()" class="btn secondary" @click="openAdd">Добавить сотрудника</button>
      <button v-if="auth.canEdit()" class="btn secondary" @click="showColumns = !showColumns">Настроить этапы</button>
      <button class="btn secondary" :disabled="exporting" @click="downloadExcel">{{ exporting ? 'Скачивание…' : 'Скачать Excel' }}</button>
      <button class="btn secondary" :disabled="loading" @click="load">Обновить</button>
    </div>
    <p v-if="exportError" role="alert" class="error">{{ exportError }}</p>
    <OnboardingColumnsModal v-if="showColumns && auth.canEdit()" :columns="columns" :refreshing="loading" :refresh-error="error" @changed="load" @close="showColumns = false" />
    <section v-if="showAdd && auth.canEdit()" class="add-panel" aria-label="Выбор сотрудника">
      <h3>Выберите сотрудника</h3>
      <form @submit.prevent="findEmployees(true)"><input v-model="employeeQuery" aria-label="Поиск сотрудника" placeholder="ФИО (от 2 символов)" /><button class="btn" :disabled="finding">Найти сотрудника</button></form>
      <p v-if="addError" role="alert" class="error">{{ addError }}</p>
      <p v-if="finding">Поиск…</p>
      <template v-else>
        <ul><li v-for="employee in employees" :key="employee.id"><span>{{ employee.full_name }} · {{ formatShortDate(employee.hire_date) }} {{ employee.status === 'dismissed' ? '(уволен)' : '' }}</span><button class="btn secondary" :disabled="adding" @click="add(employee)">Создать план</button></li></ul>
        <p v-if="!employees.length">Сотрудники не найдены.</p>
        <div class="toolbar"><button class="btn secondary" :disabled="employeePage <= 1 || adding" @click="employeePage--; findEmployees()">Назад</button><span>{{ employeePage }} / {{ employeePages || 1 }}</span><button class="btn secondary" :disabled="employeePage >= employeePages || adding" @click="employeePage++; findEmployees()">Далее</button></div>
      </template>
    </section>
    <p v-if="error" role="alert" class="error">{{ error }} <button class="btn secondary" @click="load">Повторить</button></p>
    <p v-if="loading" role="status">Загрузка…</p>
    <template v-else-if="!error">
      <p v-if="!plans.length">Планы не найдены. HR/admin может добавить сотрудника.</p>
      <div v-else class="table-scroll" tabindex="0" aria-label="Таблица планов обучения">
        <table :style="{ '--employee-count': plans.length }">
          <thead><tr><th scope="col" class="sticky">Этап / сотрудник</th><th v-for="plan in plans" :key="plan.id" scope="col">{{ plan.full_name || '—' }}<small v-if="plan.employment_status === 'dismissed'">Уволен</small></th></tr></thead>
          <tbody>
          <tr><th scope="row" class="sticky">№</th><td v-for="(plan, index) in plans" :key="plan.id">{{ (page - 1) * 25 + index + 1 }}</td></tr>
          <tr><th scope="row" class="sticky grade">Грейд</th><td v-for="plan in plans" :key="plan.id">{{ plan.grade || '—' }}</td></tr>
          <tr v-for="column in visibleColumns" :key="column.id">
            <th scope="row" class="sticky">{{ column.title }}</th>
            <td v-for="plan in plans" :key="plan.id" :class="{ completed: plan.cells[column.id]?.is_completed && !plan.cells[column.id]?.is_not_required, overdue: overdue(column, plan.cells[column.id]), 'not-required': plan.cells[column.id]?.is_not_required }">
              <button v-if="auth.canEdit()" class="cell-button" :aria-label="`${column.title}, ${plan.full_name}: ${cellLabel(plan, column)}`" @click="startEdit(plan, column)">{{ cellLabel(plan, column) }}</button>
              <span v-else>{{ cellLabel(plan, column) }}</span>
            </td>
          </tr></tbody>
        </table>
      </div>
      <footer class="toolbar"><span>Всего: {{ total }}</span><button class="btn secondary" :disabled="page <= 1" @click="changePage(-1)">Назад</button><span>{{ page }} / {{ pages || 1 }}</span><button class="btn secondary" :disabled="page >= pages" @click="changePage(1)">Далее</button></footer>
    </template>
    <OnboardingCellEditor v-if="editing && auth.canEdit()" v-bind="editing" @close="editing = null" @saved="saved" @conflict="load" />
  </section>
</template>

<style scoped>
.onboarding-page { padding: 1rem; min-width: 0; --label-width: 150px; --employee-width: 220px; }
.toolbar, form, li { display: flex; gap: .6rem; align-items: center; flex-wrap: wrap; }
.toolbar { margin: 1rem 0; }
.add-panel { padding: 1rem; border: 1px solid var(--border); }
ul { padding: 0; list-style: none; } li { justify-content: space-between; padding: .5rem 0; }
.table-scroll { overflow: auto; max-height: 65vh; }
table { border-collapse: separate; border-spacing: 0; table-layout: fixed; width: calc(var(--label-width) + var(--employee-count) * var(--employee-width)); }
th, td { box-sizing: border-box; width: var(--employee-width); padding: .65rem; border-bottom: 1px solid var(--border); overflow-wrap: anywhere; text-align: left; }
thead th { position: sticky; top: 0; background: var(--surface, #fff); z-index: 3; }
.sticky { position: sticky; left: 0; width: var(--label-width); background: var(--surface, #fff); z-index: 2; border-right: 1px solid var(--border); }
thead .sticky { z-index: 4; }
.sticky.grade { min-width: 130px; max-width: 150px; }
.cell-button { background: transparent; border: 0; color: inherit; font: inherit; cursor: pointer; text-align: left; width: 100%; min-height: 32px; white-space: pre-wrap; }
.cell-button:hover { text-decoration: underline; }
.completed { color: #16803c; background: #e2f5e9; } .overdue, .error { color: var(--danger); }
.not-required { color: var(--muted, #64748b); }
small { display: block; opacity: .7; }
@media (max-width: 640px) { .onboarding-page { --label-width: 130px; --employee-width: 190px; } }
</style>
