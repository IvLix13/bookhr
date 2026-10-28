<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import type { Employee, Paginated } from '@/types'
import type { OnboardingColumn, OnboardingCell, OnboardingDraft } from '@/types/onboarding'
import { moscowToday } from '@/utils/onboarding'
import OnboardingDialog from '@/components/OnboardingDialog.vue'
const router = useRouter()
const step = ref(0), review = ref(false), busy = ref(false), loading = ref(false)
const employee = ref<Employee>(), mentor = ref<Employee>()
const columns = ref<OnboardingColumn[]>([])
const values = ref<Record<number, Partial<OnboardingCell>>>({})
const search = ref(''), stageSearch = ref(''), missing = ref(false), page = ref(1), pages = ref(1)
const people = ref<Employee[]>([])
const error = ref(''), dirty = ref(false), menu = ref(false), discard = ref(false), saved = ref(false)
let requestId = 0, alive = true, timer: ReturnType<typeof setTimeout> | undefined
const steps = ['Сотрудник', 'Наставник', 'Мероприятия', 'Проверка']
const stages = computed(() => columns.value.filter(c => c.field_type === 'stage' || c.field_type === 'checkbox'))
const dated = computed(() => columns.value.filter(c => c.field_type === 'stage'))
const filled = computed(() => dated.value.filter(c => values.value[c.id]?.planned_date).length)
const visible = computed(() => columns.value.filter(c => c.title.toLocaleLowerCase('ru').includes(stageSearch.value.toLocaleLowerCase('ru')) && (!missing.value || (c.field_type === 'stage' && !values.value[c.id]?.planned_date))))
const eligiblePeople = computed(() => people.value.filter(p => step.value !== 1 || p.person_uuid !== employee.value?.person_uuid))
const grade = (p?: Employee) => p?.actual_grade?.name || 'Грейд не назначен'
const payload = (): OnboardingDraft => ({ employment_id: employee.value!.id, mentor_id: mentor.value!.id, cells: columns.value.map(c => ({ column_id: c.id, column_version: c.version, values: { ...values.value[c.id] } })) })
function markDirty() { dirty.value = true }
async function loadPeople(reset = false) {
  if (reset) page.value = 1
  const id = ++requestId
  loading.value = true
  try {
    const data = await api.employees({ q: search.value, active_only: step.value === 1, page: page.value, per_page: 25 }) as Paginated<Employee>
    if (!alive || id !== requestId) return
    people.value = data.items; pages.value = data.pages || 1
  } catch (err) { if (alive && id === requestId) error.value = normalizeError(err) }
  finally { if (alive && id === requestId) loading.value = false }
}
async function loadStructure() {
  loading.value = true
  try {
    const fresh = (await api.onboardingColumns()).filter(c => !c.is_archived)
    const old = new Map(columns.value.map(c => [c.id, c]))
    const retained: Record<number, Partial<OnboardingCell>> = {}
    for (const c of fresh) retained[c.id] = old.get(c.id)?.field_type === c.field_type ? { ...values.value[c.id] } : {}
    columns.value = fresh; values.value = retained
  } catch (err) { error.value = normalizeError(err) }
  finally { loading.value = false }
}
function selectPerson(p: Employee) {
  if (step.value === 0) { employee.value = p; if (mentor.value?.person_uuid === p.person_uuid) mentor.value = undefined }
  else mentor.value = p
  markDirty()
}
async function go(target: number) {
  if (busy.value) return
  error.value = ''
  if (target > 0 && !employee.value) { error.value = 'Выберите сотрудника'; return }
  if (target > 1 && !mentor.value) { error.value = 'Выберите наставника'; return }
  if (target > 2 && filled.value !== dated.value.length) {
    step.value = 2; missing.value = true; stageSearch.value = ''; error.value = 'Укажите плановые даты во всех незаполненных строках'; return
  }
  step.value = target
  if (target < 2) { search.value = ''; people.value = []; await loadPeople(true) }
}
function completed(c: OnboardingColumn) {
  const v = values.value[c.id]!
  if (c.field_type === 'stage') v.completed_date = v.is_completed ? moscowToday() : null
  markDirty()
}
async function next() {
  if (step.value < 3) await go(step.value + 1)
  else review.value = true
}
function close() {
  if (busy.value) return
  if (dirty.value) discard.value = true
  else void router.push({ name: 'onboarding' })
}
async function cancel() { dirty.value = false; discard.value = false; await router.push({ name: 'onboarding' }) }
async function finish() {
  if (busy.value) return
  if (filled.value !== dated.value.length) { review.value = false; await go(3); return }
  busy.value = true; error.value = ''; menu.value = false
  try {
    const plan = await api.createOnboardingWizard(payload())
    dirty.value = false; saved.value = true
    await router.replace({ name: 'onboarding', query: { plan: plan.id } })
  } catch (err) { error.value = `${normalizeError(err)} Если ответ был потерян, проверьте список планов перед повтором.` }
  finally { busy.value = false }
}
async function exportDraft() {
  busy.value = true; error.value = ''; menu.value = false
  try { await api.downloadOnboardingDraft(payload()) }
  catch (err) { error.value = normalizeError(err) }
  finally { busy.value = false }
}
function beforeUnload(e: BeforeUnloadEvent) { if (dirty.value && !saved.value) { e.preventDefault(); e.returnValue = '' } }
onBeforeRouteLeave(() => !dirty.value || saved.value || (!busy.value && window.confirm('Выйти без сохранения плана?')))
watch(search, () => { clearTimeout(timer); timer = setTimeout(() => { if (step.value < 2) void loadPeople(true) }, 300) })
onMounted(async () => { window.addEventListener('beforeunload', beforeUnload); await loadStructure(); await loadPeople() })
onUnmounted(() => { alive = false; requestId++; clearTimeout(timer); window.removeEventListener('beforeunload', beforeUnload) })
</script>
<template>
  <section class="card creation-page">
    <header class="page-head"><div><p>План обучения / Создание плана</p><h2>{{ review ? 'Проверьте план перед сохранением' : 'Новый план ввода в должность' }}</h2></div>
      <div v-if="review" class="menu-anchor"><button class="btn ghost" :disabled="busy" :aria-expanded="menu" aria-label="Действия с планом" @click="menu = !menu">☰</button><div v-if="menu" class="action-menu card"><button class="btn ghost" @click="exportDraft">Выгрузить план</button><button class="btn" @click="finish">Завершить</button><button class="btn ghost" @click="close">Отменить создание</button></div></div>
    </header>
    <template v-if="review"><div class="summary"><div>Сотрудник<strong>{{ employee?.full_name }}</strong>{{ grade(employee) }}</div><div>Наставник<strong>{{ mentor?.full_name }}</strong>{{ grade(mentor) }}<button class="btn secondary" :disabled="busy" @click="review = false; go(1)">Изменить наставника</button></div></div></template>
    <component :is="review ? 'div' : OnboardingDialog" v-bind="review ? {} : { title: 'Создание плана', busy }" @close="close">
      <div class="wizard" :class="{ reviewing: review }">
        <aside v-if="!review" class="rail"><h3>План ввода<br>в должность</h3><nav aria-label="Шаги создания плана"><button v-for="(label, i) in steps" :key="label" :class="{ active: step === i }" :aria-current="step === i ? 'step' : undefined" :disabled="busy" @click="go(i)"><span>{{ i < step ? '✓' : i + 1 }}</span>{{ label }}</button></nav><div class="context"><p>Сотрудник<strong>{{ employee?.full_name || 'Не выбран' }}</strong><small>{{ employee ? grade(employee) : '' }}</small></p><p>Наставник<strong>{{ mentor?.full_name || 'Не выбран' }}</strong><small>{{ mentor ? grade(mentor) : '' }}</small></p></div></aside>
        <div class="workspace">
          <header v-if="!review" class="step-head"><p>Шаг {{ step + 1 }} из 4</p><h2>{{ ['Выберите сотрудника', 'Выберите наставника', 'Назначьте плановые даты', 'План подготовлен'][step] }}</h2><p v-if="step === 2">Все {{ stages.length }} мероприятий включены в план</p></header>
          <div v-if="step < 2 && !review" class="toolbar"><input v-model="search" :disabled="busy" type="search" aria-label="Поиск сотрудников по ФИО" placeholder="Поиск по ФИО" /><span v-if="loading" role="status">Поиск…</span></div>
          <div v-if="step === 2 || review" class="toolbar"><input v-model="stageSearch" type="search" aria-label="Поиск мероприятий" placeholder="Найти мероприятие" /><label><input v-model="missing" type="checkbox" />Без даты</label><span>{{ visible.length }} из {{ columns.length }}</span></div>
          <div class="list" :aria-busy="loading">
            <template v-if="step < 2 && !review"><label v-for="p in eligiblePeople" :key="p.id" class="person" :class="{ selected: (step === 0 ? employee : mentor)?.id === p.id }"><input type="radio" name="person" :checked="(step === 0 ? employee : mentor)?.id === p.id" :disabled="busy || loading" @change="selectPerson(p)" /><span><strong>{{ p.full_name }}</strong><small>{{ grade(p) }} · Приём: {{ p.hire_date }} {{ p.status === 'dismissed' ? ' · Уволен' : '' }}</small></span></label><p v-if="!eligiblePeople.length && !loading">Сотрудники не найдены.</p></template>
            <template v-else-if="step === 2 || review"><div class="row table-head"><span>Мероприятие / поле</span><span>Плановая дата / значение</span></div><div v-for="c in visible" :key="c.id" class="row"><label :for="`field-${c.id}`">{{ c.title }}</label><div><input v-if="c.field_type === 'stage'" :id="`field-${c.id}`" v-model="values[c.id]!.planned_date" type="date" :disabled="busy" @change="markDirty" /><input v-else-if="c.field_type === 'date'" :id="`field-${c.id}`" v-model="values[c.id]!.date_value" type="date" :disabled="busy" @change="markDirty" /><input v-else-if="c.field_type === 'text'" :id="`field-${c.id}`" v-model="values[c.id]!.text_value" :disabled="busy" @input="markDirty" /><span v-else :id="`field-${c.id}`">Этап без даты</span><template v-if="review && ['stage', 'checkbox'].includes(c.field_type)"><label class="done"><input v-model="values[c.id]!.is_completed" type="checkbox" :disabled="busy" @change="completed(c)" />Выполнено</label><label v-if="c.field_type === 'stage' && values[c.id]!.is_completed" class="actual">Фактическая дата<input v-model="values[c.id]!.completed_date" type="date" :disabled="busy" @change="markDirty" /></label></template></div></div><p v-if="!visible.length">Мероприятия не найдены.</p></template>
            <div v-else class="confirmation"><h3>План подготовлен для {{ grade(employee) }} {{ employee?.full_name }}</h3><p>Наставником является {{ grade(mentor) }} {{ mentor?.full_name }}.</p><p>Включены все {{ stages.length }} мероприятий. Даты: {{ filled }} из {{ dated.length }}.</p><p>План будет сохранён после нажатия «Завершить» на странице проверки.</p></div>
          </div>
          <p v-if="error" role="alert" class="error">{{ error }} <button class="btn secondary" :disabled="busy" @click="loadStructure">Обновить структуру</button><button class="btn secondary" :disabled="busy" @click="loadPeople()">Повторить поиск</button></p>
          <footer><div><strong v-if="step >= 2 || review">Даты указаны: {{ filled }} из {{ dated.length }}</strong><small>Изменения ещё не сохранены</small></div><div v-if="step < 2 && !review" class="pagination"><button class="btn secondary" :disabled="page <= 1 || loading" @click="page--; loadPeople()">←</button>{{ page }} / {{ pages }}<button class="btn secondary" :disabled="page >= pages || loading" @click="page++; loadPeople()">→</button></div><div class="buttons"><button class="btn ghost" :disabled="busy" @click="review ? (review = false) : step > 0 ? go(step - 1) : close()">{{ review ? 'К мастеру' : step ? 'Назад' : 'Отмена' }}</button><button v-if="!review" class="btn" :disabled="busy || loading" @click="next">{{ step === 3 ? 'Открыть план' : 'Продолжить' }} →</button></div></footer>
        </div>
      </div>
    </component>
    <OnboardingDialog v-if="discard" title="Отменить создание плана?" @close="discard = false"><p>Введённые данные не будут сохранены.</p><div class="buttons"><button class="btn secondary" @click="discard = false">Продолжить создание</button><button class="btn" @click="cancel">Отменить создание</button></div></OnboardingDialog>
  </section>
</template>
<style scoped>
.creation-page{padding:1.5rem;min-width:0}.page-head{display:flex;justify-content:space-between;gap:1rem;margin-bottom:1.5rem}h2,h3,p{margin:0}p,small{color:var(--muted)}h2{font-size:1.35rem;margin:.5rem 0}.wizard{display:grid;grid-template-columns:220px minmax(0,1fr);height:min(670px,calc(100dvh - 180px));min-height:0}.rail{background:var(--bg);padding:1.2rem;border-radius:var(--radius-lg);display:flex;flex-direction:column;min-height:0}.rail h3{font-size:1.2rem}nav{display:grid;gap:.7rem;margin:1.5rem 0}nav button{display:flex;align-items:center;gap:.6rem;padding:.7rem;border:0;border-radius:var(--radius-md);background:transparent;color:var(--muted);text-align:left}nav button.active{background:var(--accent-soft);color:var(--accent)}nav button span{border-radius:50%;width:25px;height:25px;background:var(--surface);display:grid;place-items:center}.context{margin-top:auto;font-size:.8rem;overflow-wrap:anywhere}.context p{margin-top:1rem}strong,small{display:block}.workspace{display:flex;flex-direction:column;min-width:0;min-height:0;padding-left:1.5rem}.step-head{margin-bottom:1rem}.step-head p{font-size:.85rem}.toolbar{display:flex;align-items:center;gap:1rem;margin-bottom:1rem}.toolbar>input{flex:1;min-width:0}.toolbar label,.done{display:flex;align-items:center;gap:.4rem;white-space:nowrap;font-size:.85rem}input:not([type=checkbox]):not([type=radio]){padding:.6rem;border:1px solid var(--border);border-radius:var(--radius-md);min-width:0;background:var(--surface);color:var(--text);width:100%}input[type=checkbox],input[type=radio]{accent-color:var(--accent)}.list{overflow:auto;scrollbar-gutter:stable;flex:1;min-height:0}.row{display:grid;grid-template-columns:minmax(0,1fr) 185px;align-items:center;gap:1rem;padding:.8rem .6rem;border-bottom:1px solid var(--border);font-size:.9rem}.table-head{position:sticky;top:0;background:var(--bg);color:var(--muted);z-index:1;font-size:.8rem}.person{display:flex;align-items:center;gap:.8rem;padding:1rem .6rem;border-bottom:1px solid var(--border);overflow-wrap:anywhere}.person small{margin-top:.3rem}.person.selected{background:var(--accent-soft)}footer{display:flex;justify-content:space-between;align-items:center;gap:.6rem;border-top:1px solid var(--border);padding-top:1rem;margin-top:.7rem;font-size:.8rem}footer small{margin-top:.3rem}.buttons,.pagination{display:flex;gap:.5rem;align-items:center}.error{color:var(--danger);max-height:100px;overflow:auto;font-size:.85rem}.error button{padding:.3rem;margin:.3rem}.confirmation{padding:2rem 1rem}.confirmation p{margin-top:1.3rem}.reviewing{display:block;height:auto}.reviewing .workspace{padding:0}.reviewing .list{max-height:58dvh}.summary{display:flex;gap:3rem;background:var(--bg);border-radius:var(--radius);padding:1rem;margin-bottom:1rem}.summary strong{margin:.5rem 0}.summary button{margin-left:1rem}.menu-anchor{position:relative}.action-menu{position:absolute;right:0;top:100%;padding:.5rem;display:grid;gap:.5rem;z-index:3;width:220px}.done{margin-top:.6rem}.actual{display:block;font-size:.8rem;margin-top:.4rem}@media(max-width:700px){.wizard{grid-template-columns:150px minmax(0,1fr)}.rail{padding:.6rem}.workspace{padding-left:.7rem}.row{grid-template-columns:1fr}.toolbar,footer{flex-wrap:wrap}.summary{flex-wrap:wrap}}@media(max-width:480px){.wizard{grid-template-columns:1fr}.rail{display:none}.workspace{padding:0}.buttons{flex-wrap:wrap}}
</style>
