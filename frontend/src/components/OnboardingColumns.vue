<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
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
const props = defineProps<{ columns: OnboardingColumn[] }>()
const emit = defineEmits<{ changed: []; state: [value: { dirty: boolean; busy: boolean }] }>()
const draft = reactive({ id: 0, version: 0, title: '', field_type: 'stage' as OnboardingFieldType, responsible_department: '' })
const busy = ref(false)
const error = ref('')
const stale = ref(false)
const deleteTarget = ref<OnboardingColumn | null>(null)
const deleteBusy = computed(() => busy.value || !!deleteTarget.value)
const archiveTarget = ref<OnboardingColumn | null>(null)
const initialDraft = ref(JSON.stringify({ title: '', field_type: 'stage', responsible_department: '' }))
const dirty = computed(() => JSON.stringify({ title: draft.title, field_type: draft.field_type, responsible_department: draft.responsible_department }) !== initialDraft.value)
watch([dirty, deleteBusy], ([dirty, busy]) => emit('state', { dirty, busy }), { immediate: true })
function edit(column?: OnboardingColumn) {
  Object.assign(draft, { id: column?.id ?? 0, version: column?.version ?? 0, title: column?.title ?? '', field_type: column?.field_type ?? 'stage', responsible_department: column?.responsible_department ?? '' })
  initialDraft.value = JSON.stringify({ title: draft.title, field_type: draft.field_type })
  error.value = ''
  stale.value = false
}
async function run(action: () => Promise<unknown>, reset = false) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await action()
    if (reset) edit()
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
  const payload = { title: draft.title.trim(), field_type: draft.field_type, responsible_department: draft.responsible_department.trim() || null }
  return run(() => draft.id
    ? api.updateOnboardingColumn(draft.id, { ...payload, version: draft.version })
    : api.createOnboardingColumn(payload), true)
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
    <form class="column-form" @submit.prevent="save">
      <label>Название<input v-model="draft.title" required maxlength="256" :disabled="busy" /></label>
      <label>Ответственный отдел<input v-model="draft.responsible_department" maxlength="256" :disabled="busy" placeholder="Например, 3 отдел" /></label>
      <label>Тип<select v-model="draft.field_type" :disabled="busy"><option value="text">Текст</option><option value="date">Дата</option><option value="stage">Этап с датами</option><option value="checkbox">Этап без даты</option></select></label>
      <button class="btn icon-btn" :disabled="busy || stale" :aria-label="draft.id ? 'Сохранить поле' : 'Добавить поле'" :title="draft.id ? 'Сохранить поле' : 'Добавить поле'"><svg viewBox="0 0 24 24"><path :d="draft.id ? icons.save : icons.add" /></svg></button>
      <button v-if="draft.id || stale" class="btn secondary icon-btn" type="button" :disabled="busy" aria-label="Сбросить форму" title="Сбросить форму" @click="edit()"><svg viewBox="0 0 24 24"><path :d="icons.reset" /></svg></button>
    </form>
    <p>Тип заполненного поля изменить нельзя.</p>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <p v-if="stale">Список обновляется. Ввод сохранён; выберите поле заново для редактирования.</p>
    <ol>
      <li v-for="(column, index) in columns" :key="column.id">
        <span>{{ column.title }} · {{ { text: 'Текст', date: 'Дата', stage: 'Этап с датами', checkbox: 'Этап без даты' }[column.field_type] }} {{ column.responsible_department ? ' · ' + column.responsible_department : '' }} {{ column.is_archived ? '(архив)' : '' }}</span>
        <div class="actions">
          <button class="btn secondary" :disabled="busy || index === 0" :aria-label="`Переместить ${column.title} вверх`" @click="move(index, -1)" title="Вверх"><svg viewBox="0 0 24 24"><path :d="icons.up" /></svg></button>
          <button class="btn secondary" :disabled="busy || index === columns.length - 1" :aria-label="`Переместить ${column.title} вниз`" @click="move(index, 1)" title="Вниз"><svg viewBox="0 0 24 24"><path :d="icons.down" /></svg></button>
          <button class="btn secondary" :disabled="busy" @click="edit(column)" :aria-label="`Изменить ${column.title}`" title="Изменить"><svg viewBox="0 0 24 24"><path :d="icons.edit" /></svg></button>
          <button class="btn danger" :disabled="busy" @click="deleteTarget = column" :aria-label="`Удалить ${column.title}`" title="Удалить"><svg viewBox="0 0 24 24"><path :d="icons.delete" /></svg></button>
          <button class="btn secondary" :disabled="busy" @click="column.is_archived ? archive(column) : archiveTarget = column" :aria-label="`${column.is_archived ? 'Восстановить' : 'Архивировать'} ${column.title}`" :title="column.is_archived ? 'Восстановить' : 'В архив'"><svg viewBox="0 0 24 24"><path :d="column.is_archived ? icons.restore : icons.archive" /></svg></button>
        </div>
      </li>
    </ol>
    <div v-if="archiveTarget" role="alert" class="archive-confirm">
      <p>Скрыть «{{ archiveTarget.title }}» у всех сотрудников? Значения останутся сохранены.</p>
      <button class="btn" :disabled="busy" @click="archive(archiveTarget)" aria-label="Подтвердить архивирование" title="Архивировать"><svg viewBox="0 0 24 24"><path :d="icons.archive" /></svg></button>
      <button class="btn secondary" :disabled="busy" @click="archiveTarget = null" aria-label="Отменить архивирование" title="Отмена"><svg viewBox="0 0 24 24"><path :d="icons.close" /></svg></button>
    </div>
    <OnboardingDeleteDialog v-if="deleteTarget" kind="columns" :id="deleteTarget.id" :title="`Удалить поле «${deleteTarget.title}»`" @close="deleteTarget = null" @conflict="emit('changed')" @deleted="if (draft.id === deleteTarget.id) edit(); deleteTarget = null; emit('changed')" />
  </section>
</template>

<style scoped>
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
