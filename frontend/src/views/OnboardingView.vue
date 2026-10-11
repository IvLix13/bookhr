<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import { formatShortDate } from '@/utils/dates'
import OnboardingPlanCard from '@/components/OnboardingPlanCard.vue'
import { moscowToday } from '@/utils/onboarding'
import OnboardingCellEditor from '@/components/OnboardingCellEditor.vue'
import OnboardingColumnsModal from '@/components/OnboardingColumnsModal.vue'
import type { Employee, Paginated } from '@/types'
import type { OnboardingCell, OnboardingColumn, OnboardingPlan } from '@/types/onboarding'

const auth = useAuthStore()
const today = ref(moscowToday())
const expanded = ref<Set<number>>(new Set())
function togglePlan(id: number) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}
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
function namesMatch(left?: string | null, right?: string | null) {
  const own = left?.trim().toLocaleLowerCase('ru') ?? ''
  const employee = right?.trim().toLocaleLowerCase('ru') ?? ''
  return own.length > 0 && own === employee
}
function canEditCell(plan: OnboardingPlan) {
  if (auth.canEdit()) return true
  return auth.user?.role === 'viewer' && namesMatch(auth.user.full_name, plan.full_name)
}
function startEdit(plan: OnboardingPlan, column: OnboardingColumn) {
  if (!canEditCell(plan)) return
  editing.value = { planId: plan.id, employeeName: plan.full_name ?? 'Сотрудник', column: { ...column }, cell: plan.cells[column.id] ? { ...plan.cells[column.id]! } : undefined }
}
function saved() { editing.value = null; void load() }
let dayTimer: ReturnType<typeof setInterval>
onMounted(() => { void load(); dayTimer = setInterval(() => { today.value = moscowToday() }, 60000) })
onUnmounted(() => clearInterval(dayTimer))
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
    <template v-if="!error || plans.length">
      <p v-if="!plans.length && !loading">Планы не найдены. HR/admin может добавить сотрудника.</p>
      <div v-if="plans.length" class="plan-list" aria-label="Планы обучения сотрудников" :aria-busy="loading">
        <OnboardingPlanCard v-for="plan in plans" :key="plan.id" :plan="plan" :columns="visibleColumns" :today="today"
          :expanded="expanded.has(plan.id)" :editable="canEditCell(plan)" :can-manage="auth.canEdit()"
          @toggle="togglePlan(plan.id)" @edit="startEdit(plan, $event)" @changed="load" />
      </div>
      <footer class="toolbar"><span>Всего: {{ total }}</span><button class="btn secondary" :disabled="page <= 1" @click="changePage(-1)">Назад</button><span>{{ page }} / {{ pages || 1 }}</span><button class="btn secondary" :disabled="page >= pages" @click="changePage(1)">Далее</button></footer>
    </template>
    <OnboardingCellEditor v-if="editing" v-bind="editing" @close="editing = null" @saved="saved" @conflict="load" />
  </section>
</template>

<style scoped>
.onboarding-page { padding: 1.25rem; min-width: 0; }
header h2 { margin: 0; } header p { color: var(--muted); margin: .4rem 0 0; }
.toolbar, form, li { display: flex; gap: .6rem; align-items: center; flex-wrap: wrap; }
.toolbar { margin: 1rem 0; }
.toolbar input, .add-panel input { border: 1px solid var(--border); border-radius: 8px; padding: .65rem .8rem; min-width: 0; }
.plan-list { display: grid; gap: 1rem; }
.add-panel { padding: 1rem; border: 1px solid var(--border); border-radius: 12px; }
ul { padding: 0; list-style: none; } li { justify-content: space-between; padding: .5rem 0; }
.error { color: var(--danger); }
@media (max-width: 640px) { .onboarding-page { padding: .8rem; } .toolbar form { width: 100%; } .toolbar input { flex: 1; width: 120px; } }
</style>
