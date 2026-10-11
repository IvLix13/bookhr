<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import OnboardingPlanCard from '@/components/OnboardingPlanCard.vue'
import { moscowToday } from '@/utils/onboarding'
import OnboardingPlanModal from '@/components/OnboardingPlanModal.vue'
import OnboardingAddEmployeeModal from '@/components/OnboardingAddEmployeeModal.vue'
import OnboardingColumnsModal from '@/components/OnboardingColumnsModal.vue'
import type { OnboardingColumn, OnboardingPlan } from '@/types/onboarding'

const auth = useAuthStore()
const today = ref(moscowToday())
const selectedPlanId = ref<number | null>(null)
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
const exporting = ref(false)
const exportError = ref('')
let requestId = 0
async function load() {
  const id = ++requestId
  loading.value = true
  error.value = ''
  try {
    const [structure, data] = await Promise.all([api.onboardingColumns(), api.onboardingPlans({ page: page.value, per_page: 25, q: query.value })])
    if (id !== requestId) return
    columns.value = structure
    if (page.value > data.pages && page.value > 1) { page.value = Math.max(1, data.pages); await load(); return }
    plans.value = data.items
    total.value = data.total
    pages.value = data.pages
  } catch (err) { if (id === requestId) error.value = normalizeError(err) }
  finally { if (id === requestId) loading.value = false }
}
function search() { page.value = 1; void load() }
function changePage(delta: number) { page.value += delta; void load() }
async function created(plan: OnboardingPlan) {
  showAdd.value = false
  query.value = ''
  page.value = 1
  selectedPlanId.value = plan.id
  await load()
}
function deleted() { selectedPlanId.value = null; void load() }
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
let dayTimer: ReturnType<typeof setInterval>
onMounted(() => { void load(); dayTimer = setInterval(() => { today.value = moscowToday() }, 60000) })
onUnmounted(() => clearInterval(dayTimer))
</script>

<template>
  <section class="card onboarding-page">
    <header><h2>План обучения</h2><p>Ввод сотрудников в должность</p></header>
    <div class="toolbar">
      <form @submit.prevent="search"><input v-model="query" aria-label="Поиск планов по ФИО" placeholder="ФИО (от 2 символов)" /><button class="btn" :disabled="loading">Найти</button></form>
      <button v-if="auth.canEdit()" class="btn secondary" @click="showAdd = true">Добавить сотрудника</button>
      <button v-if="auth.canEdit()" class="btn secondary" @click="showColumns = !showColumns">Настроить этапы</button>
      <button class="btn secondary" :disabled="exporting" @click="downloadExcel">{{ exporting ? 'Скачивание…' : 'Скачать Excel' }}</button>
      <button class="btn secondary" :disabled="loading" @click="load">Обновить</button>
    </div>
    <p v-if="exportError" role="alert" class="error">{{ exportError }}</p>
    <OnboardingColumnsModal v-if="showColumns && auth.canEdit()" :columns="columns" :refreshing="loading" :refresh-error="error" @changed="load" @close="showColumns = false" />
    <p v-if="error" role="alert" class="error">{{ error }} <button class="btn secondary" @click="load">Повторить</button></p>
    <p v-if="loading" role="status">Загрузка…</p>
    <template v-if="!error || plans.length">
      <p v-if="!plans.length && !loading">Планы не найдены. HR/admin может добавить сотрудника.</p>
      <div v-if="plans.length" class="plan-list" aria-label="Планы обучения сотрудников" :aria-busy="loading">
        <OnboardingPlanCard v-for="plan in plans" :key="plan.id" :plan="plan" :columns="visibleColumns" :today="today" @open="selectedPlanId = plan.id" />
      </div>
      <footer class="toolbar"><span>Всего: {{ total }}</span><button class="btn secondary" :disabled="page <= 1" @click="changePage(-1)">Назад</button><span>{{ page }} / {{ pages || 1 }}</span><button class="btn secondary" :disabled="page >= pages" @click="changePage(1)">Далее</button></footer>
    </template>
    <OnboardingPlanModal v-if="selectedPlanId !== null" :key="selectedPlanId" :plan-id="selectedPlanId" :columns="visibleColumns" :today="today" @close="selectedPlanId = null" @changed="load" @deleted="deleted" />
    <OnboardingAddEmployeeModal v-if="showAdd && auth.canEdit()" @close="showAdd = false" @created="created" />
  </section>
</template>

<style scoped>
.onboarding-page { padding: 1.25rem; min-width: 0; }
header h2 { margin: 0; } header p { color: var(--muted); margin: .4rem 0 0; }
.toolbar, form, li { display: flex; gap: .6rem; align-items: center; flex-wrap: wrap; }
.toolbar { margin: 1rem 0; }
.toolbar input { border: 1px solid var(--border); border-radius: 8px; padding: .65rem .8rem; min-width: 0; }
.plan-list { display: grid; gap: 1rem; }
.error { color: var(--danger); }
@media (max-width: 640px) { .onboarding-page { padding: .8rem; } .toolbar form { width: 100%; } .toolbar input { flex: 1; width: 120px; } }
</style>
