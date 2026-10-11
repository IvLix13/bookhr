<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import { formatShortDate } from '@/utils/dates'
import OnboardingDialog from './OnboardingDialog.vue'
import type { OnboardingDeletePreview } from '@/types/onboarding'
const props = defineProps<{ kind: 'plans' | 'columns'; id: number; title: string; employmentId?: number }>()
const emit = defineEmits<{ close: []; deleted: []; conflict: [] }>()
const preview = ref<OnboardingDeletePreview | null>(null)
const busy = ref(false)
const error = ref('')
async function load() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  preview.value = null
  try { preview.value = await api.onboardingDeletePreview(props.kind, props.id) }
  catch (err) { error.value = normalizeError(err) }
  finally { busy.value = false }
}
async function remove() {
  if (busy.value || !preview.value) return
  busy.value = true
  error.value = ''
  try {
    if (props.employmentId) await api.deleteEmployeeWithPlan(props.employmentId, preview.value)
    else await api.deleteOnboarding(props.kind, props.id, preview.value)
    emit('deleted')
  } catch (err) {
    error.value = normalizeError(err)
    preview.value = null
    emit('conflict')
  } finally { busy.value = false }
}
onMounted(load)
</script>

<template>
  <OnboardingDialog :title="title" :busy="busy" @close="emit('close')">
    <p v-if="busy" role="status">Обработка…</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <template v-if="preview">
      <p v-if="preview.title">Поле: {{ preview.title }}</p>
      <p v-if="preview.full_name">{{ preview.full_name }} · {{ formatShortDate(preview.hire_date) }}</p>
      <p v-if="kind === 'columns'">Поле и все его значения будут удалены у всех сотрудников компании. Архивирование позволяет сохранить значения.</p>
      <p v-else-if="employmentId">Будут удалены выбранный период трудоустройства и его план, события и доставки, договоры, история грейдов и должностей, награды. Другие периоды трудоустройства сохранятся.</p>
      <p v-else>План, куратор и значения этапов будут удалены. Сотрудник останется в справочнике; позже можно создать новый пустой план.</p>
      <p>Ячеек для удаления: {{ preview.cell_count }}. Удаление необратимо.</p>
    </template>
    <div class="actions">
      <button v-if="!preview" class="btn secondary" :disabled="busy" @click="load">Обновить данные для подтверждения</button>
      <button v-else class="btn danger" :disabled="busy" @click="remove">Подтвердить удаление</button>
      <button class="btn secondary" :disabled="busy" @click="emit('close')">Отмена</button>
    </div>
  </OnboardingDialog>
</template>

<style scoped>
.actions { display: flex; flex-wrap: wrap; gap: .6rem; }.error { color: var(--danger); }
.btn.danger { background: var(--danger); color: #fff; border-color: var(--danger); }
</style>
