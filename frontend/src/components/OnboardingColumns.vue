<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useFocusTrap } from '@/composables/useFocusTrap'
import OnboardingColumnEditorDialog from './OnboardingColumnEditorDialog.vue'
import OnboardingDeleteDialog from './OnboardingDeleteDialog.vue'
import { api } from '@/api/client'
import { ApiError, normalizeError } from '@/api/errors'
import type { OnboardingColumn, OnboardingFieldType } from '@/types/onboarding'

const icons = {
  add: 'M12 5v14 M5 12h14', save: 'M4 4h13l3 3v13H4z M8 4v6h8V4 M8 20v-7h8v7',
  reset: 'M3 12a9 9 0 1 0 3-6 M3 3v6h6',
  up: 'M12 19V5 M5 12l7-7 7 7', down: 'M12 5v14 M5 12l7 7 7-7',
  edit: 'M12 20h9 M16 4l4 4-11 11H5v-4z',
  delete: 'M3 6h18 M8 6V4h8v2 M6 6l1 14h10l1-14 M10 10v7 M14 10v7',
  archive: 'M3 4h18v5H3z M5 9v11h14V9 M10 13h4',
  restore: 'M3 4h18v5H3z M5 9v11h14V9 M12 17v-6 M9 14l3-3 3 3',
  close: 'M5 5l14 14 M19 5L5 19',
}
const documentStages = ref<Array<{ key: string; title: string; date_placeholder: string | null; department_placeholder: string | null }>>([])
const stagesError = ref('')
async function loadDocumentStages() {
  try { documentStages.value = await api.onboardingDocumentStages(); stagesError.value = '' }
  catch (err) { stagesError.value = normalizeError(err) }
}
onMounted(loadDocumentStages)
const props = defineProps<{ columns: OnboardingColumn[] }>()
const emit = defineEmits<{ changed: []; state: [value: { dirty: boolean; busy: boolean }] }>()
const draft = reactive({ id: 0, version: 0, title: '', field_type: 'stage' as OnboardingFieldType, responsible_department: '', document_stage_key: '' })
watch(() => draft.field_type, value => { if (value !== "stage") draft.document_stage_key = "" })
const editorOpen = ref(false)
const query = ref('')
const menu = ref<OnboardingColumn | null>(null)
const menuPosition = ref({ top: '0px', left: '0px' })
const menuElement = ref<HTMLElement | null>(null)
const menuFocus = useFocusTrap(menuElement, () => !!menu.value)
watch(menu, async value => { if (value) { await nextTick(); if (menu.value) menuFocus.activate() } else menuFocus.deactivate() })
const result = ref<OnboardingColumn | null>(null)
const templateVersion = ref(0)
const templateMessage = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const typeNames = { text: 'Текст', date: 'Дата', stage: 'Этап с датами', checkbox: 'Этап без даты' }
function mapping(column: OnboardingColumn) { return documentStages.value.find(s => s.key === column.document_stage_key) }
function placeholders(column: OnboardingColumn) { const stage = column.field_type === 'stage' ? mapping(column) : undefined; return [stage?.date_placeholder, stage?.department_placeholder] }
const filtered = computed(() => props.columns.filter(c => [c.title, c.responsible_department, typeNames[c.field_type], mapping(c)?.title, ...placeholders(c)].join(' ').toLocaleLowerCase().includes(query.value.trim().toLocaleLowerCase())))
function showMenu(column: OnboardingColumn, event: MouseEvent) {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  menuPosition.value = { top: Math.max(8, Math.min(rect.bottom + 4, window.innerHeight - 260)) + 'px', left: Math.max(8, Math.min(rect.right - 230, window.innerWidth - 238)) + 'px' }
  menu.value = column
}
async function copy(value: string) { try { await navigator.clipboard.writeText(value) } catch { templateMessage.value = 'Выделите плейсхолдер и скопируйте его вручную.' } }
async function templateAction(file?: File) {
  if (busy.value) return
  busy.value = true
  templateMessage.value = ''
  try {
    if (file) { await api.uploadOnboardingTemplate(file, templateVersion.value); templateMessage.value = 'Общий шаблон компании обновлён.' }
    else await api.downloadOnboardingTemplate()
    templateVersion.value = (await api.onboardingTemplateInfo()).version
  } catch (err) { templateMessage.value = normalizeError(err); try { templateVersion.value = (await api.onboardingTemplateInfo()).version } catch {} }
  finally { busy.value = false; if (fileInput.value) fileInput.value.value = '' }
}
onMounted(async () => { try { templateVersion.value = (await api.onboardingTemplateInfo()).version } catch (err) { templateMessage.value = normalizeError(err) } })
const busy = ref(false)
const error = ref('')
const stale = ref(false)
const deleteTarget = ref<OnboardingColumn | null>(null)
const deleteBusy = computed(() => busy.value || !!deleteTarget.value || editorOpen.value)
const archiveTarget = ref<OnboardingColumn | null>(null)
const initialDraft = ref(JSON.stringify({ title: '', field_type: 'stage', responsible_department: '', document_stage_key: '' }))
const dirty = computed(() => JSON.stringify({ title: draft.title, field_type: draft.field_type, responsible_department: draft.responsible_department, document_stage_key: draft.document_stage_key }) !== initialDraft.value)
watch([dirty, deleteBusy], ([dirty, busy]) => emit('state', { dirty, busy }), { immediate: true })
function edit(column?: OnboardingColumn) {
  Object.assign(draft, { id: column?.id ?? 0, version: column?.version ?? 0, title: column?.title ?? '', field_type: column?.field_type ?? 'stage', responsible_department: column?.responsible_department ?? '', document_stage_key: column?.document_stage_key ?? '' })
  initialDraft.value = JSON.stringify({ title: draft.title, field_type: draft.field_type, responsible_department: draft.responsible_department, document_stage_key: draft.document_stage_key })
  error.value = ''
  stale.value = false
  editorOpen.value = true
  menu.value = null
}
function closeEditor() { if (!busy.value && (!dirty.value || window.confirm('Сбросить несохранённые изменения?'))) { editorOpen.value = false; initialDraft.value = JSON.stringify({ title: draft.title, field_type: draft.field_type, responsible_department: draft.responsible_department, document_stage_key: draft.document_stage_key }) } }
async function run(action: () => Promise<unknown>, reset = false) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await action()
    if (reset) { editorOpen.value = false; initialDraft.value = JSON.stringify({ title: draft.title, field_type: draft.field_type, responsible_department: draft.responsible_department, document_stage_key: draft.document_stage_key }) }
    archiveTarget.value = null
    emit('changed')
  } catch (err) {
    error.value = normalizeError(err)
    if (err instanceof ApiError && err.status === 409) {
      stale.value = true
      emit('changed')
    }
  } finally { busy.value = false }
}
function save() {
  if (stale.value) return
  const payload = { title: draft.title.trim(), field_type: draft.field_type, responsible_department: draft.responsible_department.trim() || null, document_stage_key: draft.field_type === 'stage' ? draft.document_stage_key || null : null }
  return run(() => draft.id
    ? api.updateOnboardingColumn(draft.id, { ...payload, version: draft.version }).then(value => { result.value = value })
    : api.createOnboardingColumn(payload).then(value => { result.value = value }), true)
}
function move(index: number, delta: number) {
  const next = [...props.columns]
  const item = next.splice(index, 1)[0]!
  next.splice(index + delta, 0, item)
  return run(() => api.orderOnboardingColumns(next.map(c => ({ id: c.id, version: c.version }))))
}
function archive(column: OnboardingColumn) {
  return run(() => api.updateOnboardingColumn(column.id, { version: column.version, is_archived: !column.is_archived }))
}
</script>

<template>
  <section class="card columns-panel" aria-label="Настройка этапов">
    <h3>Структура таблицы</h3>
    <p>Сотрудники отображаются карточками. Грейд и ФИО — системные данные. Этапы и поля общие для всей компании. Архивирование сохраняет значения.</p>
    <div class="table-toolbar"><input type="search" v-model="query" aria-label="Поиск по таблице" placeholder="Поиск по таблице" /><button class="btn" :disabled="busy" @click="edit()">Добавить этап</button></div>
    <div v-if="result" class="creation-result" role="status"><strong>{{ result.title }} — сохранено</strong><p>Плейсхолдеры для DOCX</p><div v-for="(value, index) in placeholders(result)" :key="index"><template v-if="value"><span>{{ index ? 'Ответственный отдел' : 'Дата этапа' }}: </span><code>{{ value }}</code> <button class="btn secondary" @click="copy(value)">Копировать</button></template></div><p v-if="!placeholders(result).some(Boolean)">Для плейсхолдеров выберите этап с датами и сопоставление в документе.</p></div>
    <OnboardingColumnEditorDialog v-if="editorOpen" @close="closeEditor" :busy="busy">
    <h3>{{ draft.id ? 'Изменить этап' : 'Добавить этап' }}</h3>
    <form class="column-form" @submit.prevent="save">
      <label>Название этапа<input v-model="draft.title" required maxlength="256" :disabled="busy" /></label>
      <label>Ответственный отдел<input v-model="draft.responsible_department" maxlength="256" :disabled="busy" placeholder="Например, 3 отдел" /></label>
      <label>Тип<select v-model="draft.field_type" :disabled="busy"><option value="text">Текст</option><option value="date">Дата</option><option value="stage">Этап с датами</option><option value="checkbox">Этап без даты</option></select></label>
      <label v-if="draft.field_type === 'stage'">Соответствует этапу в документе<select v-model="draft.document_stage_key" :disabled="busy || !!stagesError"><option value="">Не сопоставлен</option><option v-for="stage in documentStages" :key="stage.key" :value="stage.key">{{ stage.title }}</option></select></label>
      <div class="template-controls"><p>Общий шаблон плана компании. Загрузка применяется отдельно от сохранения этапа.</p><button type="button" class="btn secondary" :disabled="busy" @click="templateAction()">Скачать шаблон</button> <button type="button" class="btn secondary" :disabled="busy" @click="fileInput?.click()">Загрузить шаблон</button><input ref="fileInput" type="file" accept=".docx" hidden @change="($event.target as HTMLInputElement).files?.[0] && templateAction(($event.target as HTMLInputElement).files![0])" /><p role="status">{{ templateMessage }}</p></div>
      <button class="btn" :disabled="busy || stale">{{ draft.id ? 'Сохранить' : 'Добавить этап' }}</button><button type="button" class="btn secondary" :disabled="busy" @click="closeEditor">Отмена</button>
    </form><p v-if="error" role="alert" class="error">{{ error }}</p><p v-if="stale">Список обновлён. Откройте актуальную запись заново.</p>
    </OnboardingColumnEditorDialog>
    <p>Тип заполненного поля изменить нельзя.</p>
    <p v-if="stagesError" role="alert" class="error">{{ stagesError }} <button class="btn secondary" type="button" @click="loadDocumentStages">Повторить загрузку этапов документа</button></p>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <p v-if="stale">Список обновляется. Ввод сохранён; выберите поле заново для редактирования.</p>
    <div class="table-scroll" @scroll="menu = null"><table class="table"><thead><tr><th>Название</th><th>Ответственный отдел</th><th>Тип</th><th>Соответствует этапу в документе</th><th>Плейсхолдер даты</th><th>Плейсхолдер отдела</th><th aria-label="Действия"></th></tr></thead><tbody><tr v-for="column in filtered" :key="column.id"><td>{{ column.title }} <span v-if="column.is_archived">(архив)</span></td><td>{{ column.responsible_department || '—' }}</td><td>{{ typeNames[column.field_type] }}</td><td>{{ mapping(column)?.title || 'Не сопоставлен' }}</td><td v-for="(value, index) in placeholders(column)" :key="index"><template v-if="value"><code>{{ value }}</code><button class="btn secondary copy-button" @click="copy(value)" aria-label="Копировать плейсхолдер">⧉</button></template><span v-else>—</span></td><td><button class="btn secondary" :disabled="busy" aria-label="Действия с этапом" :aria-expanded="menu?.id === column.id" @click="showMenu(column, $event)">☰</button></td></tr><tr v-if="!filtered.length"><td colspan="7">Ничего не найдено</td></tr></tbody></table></div>
    <p>Показано {{ filtered.length }} из {{ columns.length }}</p>
    <Teleport to="body"><div v-if="menu" class="menu-backdrop" @click.self="menu = null" @keydown.esc.stop="menu = null"><div ref="menuElement" class="row-menu card" role="dialog" aria-label="Действия с этапом" tabindex="-1" :style="menuPosition"><button class="btn secondary" @click="edit(menu!)">Изменить</button><button class="btn secondary" :disabled="columns.indexOf(menu) === 0" @click="move(columns.indexOf(menu!), -1); menu = null">Вверх в общем списке</button><button class="btn secondary" :disabled="columns.indexOf(menu) === columns.length - 1" @click="move(columns.indexOf(menu!), 1); menu = null">Вниз в общем списке</button><button class="btn secondary" @click="menu.is_archived ? archive(menu) : archiveTarget = menu; menu = null">{{ menu.is_archived ? 'Восстановить' : 'Архивировать' }}</button><button class="btn danger" @click="deleteTarget = menu; menu = null">Удалить</button></div></div></Teleport>
    <div v-if="archiveTarget" role="alert" class="archive-confirm">
      <p>Скрыть «{{ archiveTarget.title }}» у всех сотрудников? Значения останутся сохранены.</p>
      <button class="btn" :disabled="busy" @click="archive(archiveTarget)" aria-label="Подтвердить архивирование" title="Архивировать"><svg viewBox="0 0 24 24"><path :d="icons.archive" /></svg></button>
      <button class="btn secondary" :disabled="busy" @click="archiveTarget = null" aria-label="Отменить архивирование" title="Отмена"><svg viewBox="0 0 24 24"><path :d="icons.close" /></svg></button>
    </div>
    <OnboardingDeleteDialog v-if="deleteTarget" kind="columns" :id="deleteTarget.id" :title="`Удалить поле «${deleteTarget.title}»`" @close="deleteTarget = null" @conflict="emit('changed')" @deleted="if (draft.id === deleteTarget.id) { result = null; editorOpen = false; } deleteTarget = null; emit('changed')" />
  </section>
</template>

<style scoped>
.columns-panel { display:flex;flex-direction:column;min-height:0;overflow:hidden; }
.table-toolbar { display:flex;justify-content:space-between;gap:1rem;margin-bottom:1rem; }
.table-toolbar input { width:min(420px,60%);padding:.65rem .8rem;border:1px solid var(--border);border-radius:var(--radius-sm); }
.table-scroll { overflow:auto;min-height:0;max-height:55dvh; }
.table { min-width:1050px; }
th { position:sticky;top:0;background:var(--accent-soft);z-index:1; }
td code { overflow-wrap:anywhere;font-size:.78rem;user-select:all; }
.copy-button { padding:.2rem .4rem;margin:.2rem; }
.creation-result { background:var(--accent-soft);padding:1rem;border-radius:var(--radius-sm);margin-bottom:1rem; }
.column-form { display:grid!important;grid-template-columns:1fr 1fr; }
.column-form label:first-child,.template-controls { grid-column:1/-1; }
.column-form input,.column-form select { width:100%;padding:.65rem;border:1px solid var(--border);border-radius:var(--radius-sm);font:inherit; }
.menu-backdrop { position:fixed;inset:0;z-index:1250; }
.row-menu { position:fixed;width:230px;display:grid;gap:.3rem;padding:.5rem; }
.row-menu button { text-align:left; }

.icon-btn { display:inline-flex;align-items:center;justify-content:center;min-width:34px;min-height:34px;padding:.4rem; }
.icon-btn svg, .actions svg, .archive-confirm svg { width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round; }
.actions button, .archive-confirm button { display:inline-flex;align-items:center;justify-content:center; }
.columns-panel { padding: 1rem; margin: 1rem 0; }
.column-form, li, .actions { display: flex; flex-wrap: wrap; align-items: center; gap: .6rem; }
label { display: grid; gap: .25rem; }
li { justify-content: space-between; padding: .6rem 0; border-bottom: 1px solid var(--border); }
ol { padding-left: 0; list-style: none; }
.error { color: var(--danger); }
.archive-confirm { padding: .8rem; border: 1px solid var(--border); }
.btn.danger { background: var(--danger); color: #fff; border-color: var(--danger); }
</style>
