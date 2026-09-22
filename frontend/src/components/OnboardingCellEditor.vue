<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api/client'
import { ApiError, normalizeError } from '@/api/errors'
import { useFocusTrap } from '@/composables/useFocusTrap'
import type { OnboardingCell, OnboardingColumn } from '@/types/onboarding'

const props = defineProps<{ planId: number; employeeName: string; column: OnboardingColumn; cell?: OnboardingCell }>()
const emit = defineEmits<{ close: []; saved: []; conflict: [] }>()
const modal = ref<HTMLElement | null>(null)
const focus = useFocusTrap(modal, () => true)
onMounted(focus.activate)
const text = ref(props.cell?.text_value ?? '')
const date = ref(props.cell?.date_value ?? '')
const planned = ref(props.cell?.planned_date ?? '')
const state = ref<'pending' | 'completed' | 'not_required'>(props.cell?.is_not_required ? 'not_required' : props.cell?.is_completed ? 'completed' : 'pending')
const isStage = computed(() => props.column.field_type === 'stage' || props.column.field_type === 'checkbox')
const clear = ref(false)
const completedDate = ref(props.cell?.completed_date ?? '')
const saving = ref(false)
const error = ref('')
const conflict = ref(false)

function changeState() {
  if (props.column.field_type === 'stage' && state.value === 'completed' && !completedDate.value) {
    completedDate.value = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Moscow' }).format(new Date())
  }
}
async function save() {
  if (saving.value || conflict.value) return
  saving.value = true
  error.value = ''
  const body: Partial<OnboardingCell> & { version: number; column_version: number; clear?: boolean } = {
    version: props.cell?.version ?? 0, column_version: props.column.version,
  }
  if (clear.value) body.clear = true
  else if (props.column.field_type === 'text') body.text_value = text.value || null
  else if (props.column.field_type === 'date') body.date_value = date.value || null
  else if (isStage.value) {
    body.is_completed = state.value === 'completed'
    body.is_not_required = state.value === 'not_required'
    if (props.column.field_type === 'stage') {
      body.planned_date = planned.value || null
      body.completed_date = state.value === 'completed' ? completedDate.value || null : null
    }
  }
  try {
    await api.updateOnboardingCell(props.planId, props.column.id, body)
    emit('saved')
  } catch (err) {
    error.value = normalizeError(err)
    if (err instanceof ApiError && err.status === 409) {
      conflict.value = true
      emit('conflict')
    }
  } finally { saving.value = false }
}
</script>

<template>
  <Teleport to="body">
    <div class="onboarding-overlay" @keydown.esc="!saving && emit('close')">
      <section ref="modal" class="card onboarding-editor" role="dialog" aria-modal="true" aria-labelledby="cell-title" tabindex="-1">
        <h3 id="cell-title">{{ column.title }} — {{ employeeName }}</h3>
        <form @submit.prevent="save">
          <fieldset :disabled="saving || clear || conflict">
          <label v-if="column.field_type === 'text'">Значение<input v-model="text" maxlength="10000" /></label>
          <label v-if="column.field_type === 'date'">Дата<input v-model="date" type="date" /></label>
          <template v-if="isStage">
            <label>Состояние<select v-model="state" aria-label="Состояние этапа" @change="changeState"><option value="pending">Не выполнено</option><option value="completed">Выполнено</option><option value="not_required">Не нужно</option></select></label>
            <label v-if="column.field_type === 'stage'">Плановая дата<input v-model="planned" type="date" :disabled="state === 'not_required'" /></label>
            <label v-if="column.field_type === 'stage' && state === 'completed'">Дата выполнения<input v-model="completedDate" type="date" required /></label>
          </template>
          </fieldset>
          <button type="button" class="btn secondary" :disabled="saving || conflict" @click="clear = !clear">{{ clear ? 'Отменить очистку' : 'Очистить ячейку' }}</button>
          <p v-if="clear" role="status">После сохранения значение, даты и отметки этой ячейки будут очищены.</p>
          <p v-if="error" role="alert" class="error">{{ error }}</p>
          <p v-if="conflict">Ваш ввод сохранён в этой форме. Скопируйте его при необходимости и откройте ячейку заново: таблица обновляется.</p>
          <div class="actions">
            <button class="btn" :disabled="saving || conflict">{{ saving ? 'Сохранение…' : 'Сохранить' }}</button>
            <button type="button" class="btn secondary" :disabled="saving" @click="emit('close')">Отмена</button>
          </div>
        </form>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.onboarding-overlay { position: fixed; inset: 0; z-index: 1100; background: #0f172a80; display: grid; place-items: center; padding: 1rem; }
.onboarding-editor { width: min(520px, 100%); padding: 1.25rem; max-height: 90vh; overflow: auto; }
label { display: grid; gap: .4rem; margin: 1rem 0; }
fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }
.check, .actions { display: flex; gap: .6rem; align-items: center; }
.error { color: var(--danger); }
</style>
