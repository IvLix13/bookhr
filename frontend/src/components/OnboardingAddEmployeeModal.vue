<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import { formatShortDate } from '@/utils/dates'
import OnboardingDialog from './OnboardingDialog.vue'
import type { Employee, Paginated } from '@/types'
import type { OnboardingPlan } from '@/types/onboarding'
const emit = defineEmits<{ close: []; created: [plan: OnboardingPlan] }>()
const query = ref('')
const page = ref(1)
const pages = ref(0)
const employees = ref<Employee[]>([])
const loading = ref(false)
const adding = ref(false)
const error = ref('')
let requestId = 0
let alive = true
async function search(reset = false) {
  if (adding.value) return
  if (reset) page.value = 1
  const id = ++requestId
  loading.value = true
  error.value = ''
  try {
    const data = await api.employees({ q: query.value, active_only: false, page: page.value, per_page: 15 }) as Paginated<Employee>
    if (!alive || id !== requestId) return
    employees.value = data.items
    pages.value = data.pages
  } catch (err) { if (alive && id === requestId) error.value = normalizeError(err) }
  finally { if (alive && id === requestId) loading.value = false }
}
async function add(employee: Employee) {
  if (adding.value || loading.value) return
  adding.value = true
  error.value = ''
  try { const plan = await api.createOnboardingPlan(employee.id); if (alive) emit('created', plan) }
  catch (err) { if (alive) error.value = normalizeError(err) }
  finally { adding.value = false }
}
onMounted(() => search(true))
onUnmounted(() => { alive = false; requestId++ })
</script>

<template>
  <OnboardingDialog title="Добавить сотрудника в план" :busy="adding" @close="emit('close')">
    <form @submit.prevent="search(true)"><input v-model="query" :disabled="adding" aria-label="Поиск сотрудника" placeholder="ФИО (от 2 символов)" /><button class="btn" :disabled="loading || adding">Найти сотрудника</button></form>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <p v-if="loading" role="status">Поиск…</p>
    <template v-else>
      <ul><li v-for="employee in employees" :key="employee.id"><span>{{ employee.full_name }} · {{ formatShortDate(employee.hire_date) }} {{ employee.status === 'dismissed' ? '(уволен)' : '' }}</span><button class="btn secondary" :disabled="adding" @click="add(employee)">Создать план</button></li></ul>
      <p v-if="!employees.length">Сотрудники не найдены.</p>
      <div class="actions"><button class="btn secondary" :disabled="page <= 1 || adding" @click="page--; search()">Назад</button><span>{{ page }} / {{ pages || 1 }}</span><button class="btn secondary" :disabled="page >= pages || adding" @click="page++; search()">Далее</button></div>
    </template>
    <footer><button class="btn secondary" :disabled="adding" @click="emit('close')">Отмена</button></footer>
  </OnboardingDialog>
</template>

<style scoped>
form, li, .actions { display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; }input { min-width: 0; flex: 1; border: 1px solid var(--border); padding: .65rem; border-radius: 8px; }ul { list-style: none; padding: 0; }li { justify-content: space-between; padding: .6rem 0; }li span { overflow-wrap: anywhere; }footer { display: flex; justify-content: flex-end; margin-top: 1rem; }.error { color: var(--danger); }
</style>
