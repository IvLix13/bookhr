<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { api } from '@/api/client'
import { ApiError, normalizeError } from '@/api/errors'
import { formatShortDate } from '@/utils/dates'
import { cellLabel, stageLabels, stageState } from '@/utils/onboarding'
import type { OnboardingColumn, OnboardingPlan } from '@/types/onboarding'

const props = defineProps<{ plan: OnboardingPlan; columns: OnboardingColumn[]; today: string; editable: boolean; canManage: boolean }>()
const emit = defineEmits<{ edit: [column: OnboardingColumn]; changed: []; state: [value: { dirty: boolean; busy: boolean }] }>()
const curatorEditing = ref(false)
const curator = ref('')
const curatorVersion = ref(0)
const initialCurator = ref('')
const dirty = computed(() => curatorEditing.value && curator.value !== initialCurator.value)
const curatorSaving = ref(false)
const curatorError = ref('')
const curatorConflict = ref(false)
watch([dirty, curatorSaving], ([dirty, busy]) => emit('state', { dirty, busy }))
function editCurator() {
  curator.value = props.plan.curator_name ?? ''
  initialCurator.value = curator.value
  curatorVersion.value = props.plan.version
  curatorError.value = ''
  curatorConflict.value = false
  curatorEditing.value = true
}
async function saveCurator() {
  if (curatorSaving.value || curatorConflict.value || !props.canManage) return
  curatorSaving.value = true
  curatorError.value = ''
  try {
    await api.updateOnboardingPlan(props.plan.id, { version: curatorVersion.value, curator_name: curator.value.trim() || null })
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
        <input :id="`curator-${plan.id}`" v-model="curator" maxlength="256" :disabled="curatorSaving || curatorConflict || !canManage" />
        <div class="form-actions"><button class="btn" :disabled="curatorSaving || curatorConflict || !canManage">{{ curatorSaving ? 'Сохранение…' : 'Сохранить куратора' }}</button><button type="button" class="btn secondary" :disabled="curatorSaving" @click="curatorEditing = false">Отмена</button></div>
        <p v-if="curatorError" role="alert" class="error">{{ curatorError }}</p>
        <p v-if="curatorConflict">Ваш ввод сохранён. Закройте форму и откройте её снова для редактирования актуальной версии.</p>
      </form>
      <p v-if="!columns.length" class="muted">Этапы пока не настроены.</p>
      <div v-else class="details-scroll">
        <table>
          <thead><tr><th scope="col">Этап / поле</th><th scope="col">Ответственный отдел</th><th scope="col">Состояние / значение</th><th scope="col">Плановый срок</th><th scope="col">Выполнено</th></tr></thead>
          <tbody><tr v-for="column in columns" :key="column.id">
            <th scope="row">{{ column.title }}</th><td>{{ column.responsible_department || "—" }}</td>
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
