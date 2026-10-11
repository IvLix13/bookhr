<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
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
const state = ref({ dirty: false, busy: false })
function updateState(value: { dirty: boolean; busy: boolean }) {
  state.value.dirty = value.dirty
  state.value.busy = value.busy
}
const discard = ref(false)
const deletion = ref<'plan' | 'employee' | null>(null)
const editing = ref<{ column: OnboardingColumn; cell?: OnboardingCell } | null>(null)
const today = computed(() => props.today ?? moscowToday())
const summary = computed(() => plan.value ? planSummary(plan.value, props.columns, today.value) : null)
const editable = computed(() => auth.canEdit() || (auth.user?.role === 'viewer' && !!auth.user.full_name?.trim() && auth.user.full_name.trim().toLocaleLowerCase('ru') === plan.value?.full_name?.trim().toLocaleLowerCase('ru')))
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
  if (state.value.busy || editing.value || deletion.value) return
  if (state.value.dirty) discard.value = true
  else emit('close')
}
function changed() { void load(); emit('changed') }
function saved() { editing.value = null; changed() }
function startEdit(column: OnboardingColumn) {
  if (!plan.value || !editable.value || state.value.busy) return
  editing.value = { column: { ...column }, cell: plan.value.cells[column.id] ? { ...plan.value.cells[column.id]! } : undefined }
}
watch(() => props.columns.map(c => `${c.id}:${c.version}`).join(','), load)
onMounted(load)
</script>

<template>
  <OnboardingDialog :title="`План — ${plan?.full_name || 'Сотрудник'}`" :busy="state.busy || !!editing || !!deletion || discard" @close="close">
    <OnboardingDialog v-if="discard" title="Несохранённые изменения" @close="discard = false">
      <p>Есть несохранённые изменения. Закрыть окно и сбросить их?</p>
      <button class="btn" @click="discard = false">Продолжить редактирование</button>
      <button class="btn secondary" @click="emit('close')">Закрыть без сохранения</button>
    </OnboardingDialog>
    <div key="plan-content">
      <p v-if="loading" role="status">Загрузка плана…</p>
      <p v-if="error" role="alert" class="error">{{ error }} <button class="btn secondary" @click="load">Повторить загрузку</button></p>
      <template v-if="plan">
        <p>{{ plan.grade || 'Грейд не назначен' }} · Прибыл: {{ formatShortDate(summary?.arrival) }} · {{ summary?.department || 'Отдел не указан' }}</p>
        <p>Куратор: {{ plan.curator_name || 'Не назначен' }}</p>
        <p>Выполнено {{ summary?.counts.completed }}/{{ summary?.total }} · {{ summary?.percent }}%</p>
        <OnboardingPlanDetails :key="plan.id" :plan="plan" :columns="columns" :today="today" :editable="editable && !loading && !error" :can-manage="auth.canEdit() && !loading && !error" @edit="startEdit" @changed="changed" @state="updateState" />
        <div v-if="auth.canEdit()" class="actions">
          <button class="btn secondary" :disabled="state.busy || state.dirty || loading || !!error" @click="deletion = 'plan'">Удалить план</button>
          <button class="btn danger" :disabled="state.busy || state.dirty || loading || !!error" @click="deletion = 'employee'">Удалить сотрудника и план</button>
        </div>
      </template>
      <footer><button class="btn secondary" :disabled="state.busy" @click="close">Закрыть</button></footer>
    </div>
    <OnboardingCellEditor v-if="editing && plan" :plan-id="plan.id" :employee-name="plan.full_name || 'Сотрудник'" v-bind="editing" @close="editing = null" @saved="saved" @conflict="changed" />
    <OnboardingDeleteDialog v-if="deletion && plan" kind="plans" :id="plan.id" :employment-id="deletion === 'employee' ? plan.employment_id : undefined" :title="deletion === 'employee' ? 'Удалить сотрудника и план' : 'Удалить план'" @close="deletion = null" @deleted="emit('deleted')" @conflict="changed" />
  </OnboardingDialog>
</template>

<style scoped>
.actions { display: flex; gap: .6rem; flex-wrap: wrap; margin-top: 1rem; }footer { display: flex; justify-content: flex-end; margin-top: 1rem; }.error { color: var(--danger); }
.btn.danger { background: var(--danger); color: #fff; border-color: var(--danger); }
</style>
