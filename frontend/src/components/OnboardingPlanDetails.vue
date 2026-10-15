<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { api } from '@/api/client'
import { ApiError, normalizeError } from '@/api/errors'
import { formatShortDate } from '@/utils/dates'
import { cellLabel, stageLabels, stageState } from '@/utils/onboarding'
import type { Employee, Paginated } from '@/types'
import type { OnboardingColumn, OnboardingPlan } from '@/types/onboarding'

const props = defineProps<{ plan: OnboardingPlan; columns: OnboardingColumn[]; today: string; editable: boolean; canManage: boolean }>()
const emit = defineEmits<{ edit: [column: OnboardingColumn]; changed: []; state: [value: { dirty: boolean; busy: boolean }] }>()
const curatorEditing = ref(false)
const curator = ref('')
const curatorId = ref<number | null>(null)
const initialCuratorId = ref<number | null>(null)
const searchResults = ref<Employee[]>([])
const searchBusy = ref(false)
const searchError = ref('')
const searchPage = ref(1)
const searchPages = ref(0)
let searchRequest = 0
async function searchCurator(reset = true) {
  if (reset) searchPage.value = 1
  const id = ++searchRequest
  searchBusy.value = true
  searchError.value = ''
  try {
    const result = await api.employees({ q: curator.value, active_only: true, page: searchPage.value, per_page: 15 }) as Paginated<Employee>
    if (id === searchRequest) {
      searchResults.value = result.items.filter(item => item.id !== props.plan.employment_id)
      searchPages.value = result.pages
    }
  } catch (err) { if (id === searchRequest) searchError.value = normalizeError(err) }
  finally { if (id === searchRequest) searchBusy.value = false }
}
function chooseCurator(employee: Employee) {
  curatorId.value = employee.id
  curator.value = employee.full_name || ''
  searchResults.value = []
  searchPages.value = 0
}
function clearCurator() {
  curatorId.value = null
  curator.value = ''
  searchResults.value = []
  searchPages.value = 0
}
function curatorTyped() { curatorId.value = null }
const curatorVersion = ref(0)
const initialCurator = ref('')
const dirty = computed(() => curatorEditing.value && (curator.value !== initialCurator.value || curatorId.value !== initialCuratorId.value))
const curatorSaving = ref(false)
const curatorError = ref('')
const curatorConflict = ref(false)
watch([dirty, curatorSaving], ([dirty, busy]) => emit('state', { dirty, busy }))
function editCurator() {
  curator.value = props.plan.curator_name ?? ''
  curatorId.value = props.plan.curator_employment_id ?? null
  initialCuratorId.value = curatorId.value
  searchResults.value = []
  searchError.value = ''
  searchPages.value = 0
  initialCurator.value = curator.value
  curatorVersion.value = props.plan.version
  curatorError.value = ''
  curatorConflict.value = false
  curatorEditing.value = true
}
async function saveCurator() {
  if (curatorSaving.value || curatorConflict.value || !props.canManage) return
  if (curator.value.trim() && curatorId.value === null) { curatorError.value = 'Выберите куратора из результатов поиска'; return }
  curatorSaving.value = true
  curatorError.value = ''
  try {
    await api.updateOnboardingPlan(props.plan.id, { version: curatorVersion.value, curator_employment_id: curatorId.value })
    curatorEditing.value = false
    emit('changed')
  } catch (err) {
    curatorError.value = normalizeError(err)
    if (err instanceof ApiError && err.status === 409) { curatorConflict.value = true; emit('changed') }
  } finally { curatorSaving.value = false }
}
function isStage(column: OnboardingColumn) { return column.field_type === 'stage' || column.field_type === 'checkbox' }
</script>

<template>
    <section :id="`plan-details-${plan.id}`" class="plan-details" :aria-label="`Этапы: ${plan.full_name}`">
      <div class="details-header">
        <h4>Этапы и данные плана</h4>
        <button v-if="canManage && !curatorEditing" class="btn secondary" @click="editCurator">Изменить куратора</button>
      </div>
      <form v-if="curatorEditing" class="curator-form" @submit.prevent="saveCurator">
        <label :for="`curator-${plan.id}`">ФИО куратора</label>
        <input :id="`curator-${plan.id}`" v-model="curator" maxlength="256" @input="curatorTyped" :disabled="curatorSaving || curatorConflict || !canManage" />
        <div class="form-actions"><button type="button" class="btn secondary" :disabled="searchBusy || curatorSaving || curatorConflict" @click="searchCurator()">Найти куратора</button><button type="button" class="btn secondary" :disabled="curatorSaving || curatorConflict" @click="clearCurator">Убрать куратора</button></div>
        <p v-if="searchBusy" role="status">Поиск…</p>
        <p v-if="searchError" role="alert" class="error">{{ searchError }}</p>
        <ul v-if="searchResults.length"><li v-for="employee in searchResults" :key="employee.id">{{ employee.full_name }} · {{ formatShortDate(employee.hire_date) }} <button type="button" class="btn secondary" :disabled="curatorSaving || curatorConflict || searchBusy" @click="chooseCurator(employee)">Выбрать куратора</button></li></ul>
        <div v-if="searchPages > 0" class="form-actions"><button type="button" class="btn secondary" :disabled="searchPage <= 1 || searchBusy || curatorSaving || curatorConflict" @click="searchPage--; searchCurator(false)">Назад</button><span>{{ searchPage }} / {{ searchPages }}</span><button type="button" class="btn secondary" :disabled="searchPage >= searchPages || searchBusy || curatorSaving || curatorConflict" @click="searchPage++; searchCurator(false)">Далее</button></div>
        <p v-if="curator && !curatorId">Найдите и выберите сотрудника для назначения куратора.</p>
        <div class="form-actions"><button class="btn" :disabled="curatorSaving || curatorConflict || !canManage">{{ curatorSaving ? 'Сохранение…' : 'Сохранить куратора' }}</button><button type="button" class="btn secondary" :disabled="curatorSaving" @click="curatorEditing = false">Отмена</button></div>
        <p v-if="curatorError" role="alert" class="error">{{ curatorError }}</p>
        <p v-if="curatorConflict">Ваш ввод сохранён. Закройте форму и откройте её снова для редактирования актуальной версии.</p>
      </form>
      <p v-if="!columns.length" class="muted">Этапы пока не настроены.</p>
      <div v-else class="details-scroll">
        <table>
          <thead><tr><th scope="col">Этап / поле</th><th scope="col">Состояние / значение</th><th scope="col">Плановый срок</th><th scope="col">Выполнено</th></tr></thead>
          <tbody><tr v-for="column in columns" :key="column.id">
            <th scope="row">{{ column.title }}</th>
            <td :class="isStage(column) ? stageState(column, plan.cells[column.id], today).replace('_', '-') : ''">
              <button v-if="editable" type="button" class="cell-button" :aria-label="`${column.title}, ${plan.full_name}: ${cellLabel(plan, column)}`" @click="emit('edit', column)">{{ isStage(column) ? stageLabels[stageState(column, plan.cells[column.id], today)] : cellLabel(plan, column) }}</button>
              <span v-else>{{ isStage(column) ? stageLabels[stageState(column, plan.cells[column.id], today)] : cellLabel(plan, column) }}</span>
            </td>
            <td>{{ column.field_type === 'stage' && !plan.cells[column.id]?.is_not_required ? formatShortDate(plan.cells[column.id]?.planned_date) : '—' }}</td>
            <td>{{ column.field_type === 'stage' && plan.cells[column.id]?.is_completed ? formatShortDate(plan.cells[column.id]?.completed_date) : '—' }}</td>
          </tr></tbody>
        </table>
      </div>
    </section>
</template>
<style scoped>
.plan-details { border-top: 1px solid var(--border); padding: 1rem 1.5rem 1.4rem; background: var(--bg); }
.details-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: .7rem; margin-bottom: .8rem; } h4 { margin: 0; }
.details-scroll { overflow-x: auto; } table { width: 100%; border-collapse: collapse; font-size: .9rem; } th, td { padding: .7rem .6rem; border-bottom: 1px solid var(--border); text-align: left; overflow-wrap: anywhere; min-width: 110px; }
thead th { color: var(--muted); font-weight: 500; } tbody th { width: 30%; font-weight: 500; min-width: 150px; }
.cell-button { background: transparent; border: 0; color: inherit; font: inherit; cursor: pointer; text-align: left; width: 100%; min-height: 32px; padding: 0; white-space: pre-wrap; } .cell-button:hover { text-decoration: underline; }
.completed { color: #16803c; background: #e2f5e9; } .overdue { color: #b73535; background: #fdecec; } .in-progress { color: #886200; background: #fff4df; } .not-required { color: var(--muted); }
.curator-form { display: grid; gap: .6rem; max-width: 600px; margin: 0 0 1rem; } .curator-form input { padding: .65rem; border: 1px solid var(--border); border-radius: 8px; width: 100%; } .curator-form p { margin: 0; } .form-actions { display: flex; flex-wrap: wrap; gap: .6rem; } .error { color: var(--danger); }
.muted { color: var(--muted); }
@media (max-width: 640px) { .plan-details { padding: .8rem; } }
</style>
