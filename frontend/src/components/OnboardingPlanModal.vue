<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, useId, watch } from 'vue'
import { api } from '@/api/client'
import { ApiError, normalizeError } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import { formatShortDate } from '@/utils/dates'
import { planSummary, moscowToday } from '@/utils/onboarding'
import OnboardingDialog from './OnboardingDialog.vue'
import OnboardingPlanDetails from './OnboardingPlanDetails.vue'
import OnboardingCellEditor from './OnboardingCellEditor.vue'
import OnboardingDeleteDialog from './OnboardingDeleteDialog.vue'
import type { OnboardingColumn, OnboardingPlan, OnboardingCell } from '@/types/onboarding'
const props = defineProps<{ planId: number; columns: OnboardingColumn[]; today?: string }>()
const emit = defineEmits<{ close: []; changed: []; deleted: [] }>()
const auth = useAuthStore()
const plan = ref<OnboardingPlan | null>(null)
const loading = ref(false)
const error = ref('')
const curatorEditing = ref(false)
const curator = ref('')
const curatorVersion = ref(0)
const initialCurator = ref('')
const dirty = computed(() => curatorEditing.value && curator.value !== initialCurator.value)
const curatorSaving = ref(false)
const curatorError = ref('')
const curatorConflict = ref(false)
const state = computed(() => ({ dirty: dirty.value, busy: curatorSaving.value }))
function editCurator() {
  if (blocked.value) return
  closeMenu()
  void nextTick(() => mentorInput.value?.focus())
  curator.value = plan.value?.curator_name ?? ''
  initialCurator.value = curator.value
  curatorVersion.value = plan.value?.version ?? 0
  curatorError.value = ''
  curatorConflict.value = false
  curatorEditing.value = true
}
async function saveCurator() {
  if (curatorSaving.value || curatorConflict.value || !auth.canEdit() || loading.value || !!error.value) return
  curatorSaving.value = true
  curatorError.value = ''
  try {
    await api.updateOnboardingPlan(plan.value!.id, { version: curatorVersion.value, curator_name: curator.value.trim() || null })
    curatorEditing.value = false
    changed()
  } catch (err) {
    curatorError.value = normalizeError(err)
    if (err instanceof ApiError && err.status === 409) { curatorConflict.value = true; changed() }
  } finally { curatorSaving.value = false }
}
const discard = ref(false)
const deletion = ref<'plan' | 'employee' | null>(null)
const editing = ref<{ column: OnboardingColumn; cell?: OnboardingCell } | null>(null)
const today = computed(() => props.today ?? moscowToday())
const summary = computed(() => plan.value ? planSummary(plan.value, props.columns, today.value) : null)
const editable = computed(() => auth.canEdit() || (auth.user?.role === 'viewer' && !!auth.user.full_name?.trim() && auth.user.full_name.trim().toLocaleLowerCase('ru') === plan.value?.full_name?.trim().toLocaleLowerCase('ru')))
const exporting = ref(false)
const exportError = ref('')
async function exportPlan() {
  if (blocked.value || !plan.value) return
  closeMenu()
  exporting.value = true
  exportError.value = ''
  try { await api.downloadOnboardingDocx(plan.value.id) }
  catch (err) { exportError.value = normalizeError(err) }
  finally { exporting.value = false }
}
const menu = ref(false)
const menuAnchor = ref<HTMLElement | null>(null)
const menuButton = ref<HTMLButtonElement | null>(null)
const mentorInput = ref<HTMLInputElement | null>(null)
const menuId = useId()
const blocked = computed(() => loading.value || !!error.value || !plan.value || state.value.busy || state.value.dirty || !!editing.value || !!deletion.value || discard.value || exporting.value)
function closeMenu() { if (menu.value) { menu.value = false; menuButton.value?.focus() } }
function consumeEscape() { if (!menu.value) return false; closeMenu(); return true }
function menuEscape(event: KeyboardEvent) { if (menu.value) { event.stopPropagation(); event.preventDefault(); closeMenu() } }
function outside(event: PointerEvent) { if (menu.value && event.target instanceof Node && !menuAnchor.value?.contains(event.target)) closeMenu() }
function remove(kind: 'plan' | 'employee') { if (blocked.value) return; closeMenu(); deletion.value = kind }
onMounted(() => document.addEventListener('pointerdown', outside))
onUnmounted(() => document.removeEventListener('pointerdown', outside))
let requestId = 0
async function load() {
  const id = ++requestId
  loading.value = true
  error.value = ''
  try {
    const data = await api.onboardingPlan(props.planId)
    if (id === requestId) plan.value = data
  } catch (err) { if (id === requestId) error.value = normalizeError(err) }
  finally { if (id === requestId) loading.value = false }
}
function close() {
  closeMenu()
  if (state.value.busy || editing.value || deletion.value) return
  if (state.value.dirty) discard.value = true
  else emit('close')
}
function changed() { void load(); emit('changed') }
function saved() { editing.value = null; changed() }
function startEdit(column: OnboardingColumn) {
  if (!plan.value || !editable.value || state.value.busy || state.value.dirty || loading.value || !!error.value) return
  closeMenu()
  editing.value = { column: { ...column }, cell: plan.value.cells[column.id] ? { ...plan.value.cells[column.id]! } : undefined }
}
watch(() => props.columns.map(c => `${c.id}:${c.version}`).join(','), load)
onMounted(load)
</script>

<template>
  <OnboardingDialog title="План сотрудника" layout="plan" :consume-escape="consumeEscape" :busy="state.busy || !!editing || !!deletion || discard" @close="close">
    <template #header-actions>
      <div ref="menuAnchor" class="menu-anchor" @keydown.esc="menuEscape">
        <button ref="menuButton" class="btn secondary" :disabled="state.busy || !!editing || !!deletion || discard" aria-label="Действия с планом" :aria-controls="menuId" :aria-expanded="menu" @click="menu = !menu">☰</button>
        <div v-if="menu" :id="menuId" class="action-menu">
          <button class="btn ghost" :disabled="blocked" @click="exportPlan">{{ exporting ? 'Выгрузка…' : 'Выгрузить план' }}</button>
          <button v-if="auth.canEdit()" class="btn ghost" :disabled="blocked" @click="editCurator">Изменить наставника</button>
          <hr v-if="auth.canEdit()" />
          <button v-if="auth.canEdit()" class="btn ghost danger" :disabled="blocked" @click="remove('plan')">Удалить план</button>
          <button v-if="auth.canEdit()" class="btn ghost danger" :disabled="blocked" @click="remove('employee')">Удалить сотрудника и план</button>
          <hr /><button class="btn ghost" :disabled="state.busy" @click="close">Закрыть окно</button>
        </div>
      </div>
    </template>
    <OnboardingDialog v-if="discard" title="Несохранённые изменения" @close="discard = false">
      <p>Есть несохранённые изменения. Закрыть окно и сбросить их?</p>
      <button class="btn" @click="discard = false">Продолжить редактирование</button>
      <button class="btn secondary" @click="emit('close')">Закрыть без сохранения</button>
    </OnboardingDialog>
    <div key="plan-content" class="plan-content">
      <p v-if="loading" role="status">Загрузка плана…</p>
      <p v-if="error" role="alert" class="error">{{ error }} <button class="btn secondary" @click="load">Повторить загрузку</button></p>
      <template v-if="plan">
        <section class="employee-summary" :aria-label="`Сведения: ${plan.full_name || 'Сотрудник'}`">
          <h3>{{ plan.full_name || 'Сотрудник' }}</h3><p class="muted">{{ summary?.department || 'Отдел не указан' }} · Прибыл {{ formatShortDate(summary?.arrival) }}</p>
          <span v-if="plan.employment_status === 'dismissed'" class="badge danger">Уволен</span>
          <div class="facts-grid"><div class="fact"><span>Грейд</span><strong class="grade">{{ plan.grade || 'Грейд не назначен' }}</strong></div><div class="fact"><span>Наставник</span><strong>{{ plan.curator_name || 'Не назначен' }}</strong></div><div class="fact" v-if="summary"><div class="progress-caption"><span>Выполнение плана</span><strong>{{ summary.percent }}%</strong></div><div class="progress-track" role="progressbar" aria-label="Выполнение плана" :aria-valuenow="summary.percent" aria-valuemin="0" aria-valuemax="100" :aria-valuetext="summary.total ? `Выполнено ${summary.counts.completed} из ${summary.total}` : 'Нет обязательных этапов'"><span v-for="(count, key) in { done: summary.counts.completed, working: summary.counts.in_progress, late: summary.counts.overdue }" :key="key" :class="key" :style="{ width: `${summary.total ? count / summary.total * 100 : 0}%` }" /></div><small>{{ summary.total ? `Выполнено ${summary.counts.completed} из ${summary.total} этапов` : 'Нет обязательных этапов' }}</small></div></div>
        </section>
      <form v-if="curatorEditing" class="curator-form" @submit.prevent="saveCurator">
        <label :for="`curator-${plan.id}`">ФИО наставника</label>
        <input ref="mentorInput" :id="`curator-${plan.id}`" v-model="curator" maxlength="256" :disabled="curatorSaving || curatorConflict || (!auth.canEdit() || loading || !!error)" />
        <div class="form-actions"><button class="btn" :disabled="curatorSaving || curatorConflict || (!auth.canEdit() || loading || !!error)">{{ curatorSaving ? 'Сохранение…' : 'Сохранить наставника' }}</button><button type="button" class="btn secondary" :disabled="curatorSaving" @click="curatorEditing = false">Отмена</button></div>
        <p v-if="curatorError" role="alert" class="error">{{ curatorError }}</p>
        <p v-if="curatorConflict">Ваш ввод сохранён. Закройте форму и откройте её снова для редактирования актуальной версии.</p>
      </form>
        <OnboardingPlanDetails :key="plan.id" :plan="plan" :columns="columns" :today="today" :editable="editable && !loading && !error && !state.dirty && !state.busy" @edit="startEdit" />
      </template>
      <p v-if="exportError" role="alert" class="error">{{ exportError }}</p>

    </div>
    <OnboardingCellEditor v-if="editing && plan" :plan-id="plan.id" :employee-name="plan.full_name || 'Сотрудник'" v-bind="editing" @close="editing = null" @saved="saved" @conflict="changed" />
    <OnboardingDeleteDialog v-if="deletion && plan" kind="plans" :id="plan.id" :employment-id="deletion === 'employee' ? plan.employment_id : undefined" :title="deletion === 'employee' ? 'Удалить сотрудника и план' : 'Удалить план'" @close="deletion = null" @deleted="emit('deleted')" @conflict="changed" />
  </OnboardingDialog>
</template>

<style scoped>
.plan-content { display: flex; flex-direction: column; flex: 1; min-height: 0; min-width: 0; gap: 1rem; }
.employee-summary { flex-shrink: 0; } h3 { margin: 0; font-size: 1.5rem; overflow-wrap: anywhere; } .muted { color: var(--muted); margin: .5rem 0 1rem; }
.facts-grid { display: grid; grid-template-columns: minmax(0,.6fr) minmax(0,1.2fr) minmax(0,1.2fr); gap: 1rem; }
.fact { min-width: 0; padding: 1rem; border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--bg); } .fact span, small { color: var(--muted); font-size: .85rem; } .fact strong { display: block; margin-top: .4rem; overflow-wrap: anywhere; font-weight: 500; } .fact .grade { color: var(--accent); font-size: 1.25rem; }
.progress-caption { display: flex; justify-content: space-between; gap: .5rem; align-items: center; margin-bottom: .6rem; } .progress-caption strong { margin: 0; font-variant-numeric: tabular-nums; }
.progress-track { height: 12px; display: flex; border-radius: var(--radius-pill); background: var(--border); overflow: hidden; margin-bottom: .5rem; } .progress-track span { flex-shrink: 0; } .done { background: #1fa66a; } .working { background: #e8b838; } .late { background: #dc6262; }
.menu-anchor { position: relative; } .action-menu { position: absolute; right: 0; top: calc(100% + .5rem); width: min(300px, calc(100vw - 4rem)); background: var(--surface); padding: .5rem; border: 1px solid var(--border); border-radius: var(--radius-lg); box-shadow: var(--shadow); display: grid; gap: .3rem; z-index: 10; } .action-menu button { text-align: left; border: 0; } .action-menu hr { width: 100%; border: 0; border-top: 1px solid var(--border); } .action-menu .danger { color: var(--danger); }
.curator-form { flex-shrink: 0; display: grid; gap: .6rem; max-width: 600px; } .curator-form input { padding: .65rem; border: 1px solid var(--border); border-radius: 8px; width: 100%; } .curator-form p { margin: 0; } .form-actions { display: flex; flex-wrap: wrap; gap: .6rem; } .error { color: var(--danger); flex-shrink: 0; }
@media (max-width: 640px) { .facts-grid { grid-template-columns: 1fr; } }
@media (max-width: 640px), (max-height: 650px) { .plan-content { flex: none; } }
</style>
