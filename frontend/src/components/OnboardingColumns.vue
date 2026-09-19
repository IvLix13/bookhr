<script setup lang="ts">
import { reactive, ref } from 'vue'
import { api } from '@/api/client'
import { ApiError, normalizeError } from '@/api/errors'
import type { OnboardingColumn, OnboardingFieldType } from '@/types/onboarding'

const props = defineProps<{ columns: OnboardingColumn[] }>()
const emit = defineEmits<{ changed: [] }>()
const draft = reactive({ id: 0, version: 0, title: '', field_type: 'stage' as OnboardingFieldType })
const busy = ref(false)
const error = ref('')
const stale = ref(false)
const archiveTarget = ref<OnboardingColumn | null>(null)
function edit(column?: OnboardingColumn) {
  Object.assign(draft, { id: column?.id ?? 0, version: column?.version ?? 0, title: column?.title ?? '', field_type: column?.field_type ?? 'stage' })
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
  const payload = { title: draft.title.trim(), field_type: draft.field_type }
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
  <section class="card columns-panel" aria-label="Настройка столбцов">
    <h3>Структура таблицы</h3>
    <p>Номер, Грейд и ФИО — системные. Остальные столбцы общие для всей компании. Архивирование сохраняет значения.</p>
    <form class="column-form" @submit.prevent="save">
      <label>Название<input v-model="draft.title" required maxlength="256" :disabled="busy" /></label>
      <label>Тип<select v-model="draft.field_type" :disabled="busy"><option value="text">Текст</option><option value="date">Дата</option><option value="stage">Этап с датами</option></select></label>
      <button class="btn" :disabled="busy || stale">{{ draft.id ? 'Сохранить столбец' : 'Добавить столбец' }}</button>
      <button v-if="draft.id || stale" class="btn secondary" type="button" :disabled="busy" @click="edit()">Сбросить форму</button>
    </form>
    <p>Тип заполненного столбца изменить нельзя.</p>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <p v-if="stale">Список обновляется. Ввод сохранён; выберите столбец заново для редактирования.</p>
    <ol>
      <li v-for="(column, index) in columns" :key="column.id">
        <span>{{ column.title }} · {{ { text: 'Текст', date: 'Дата', stage: 'Этап' }[column.field_type] }} {{ column.is_archived ? '(архив)' : '' }}</span>
        <div class="actions">
          <button class="btn secondary" :disabled="busy || index === 0" :aria-label="`Переместить ${column.title} влево`" @click="move(index, -1)">←</button>
          <button class="btn secondary" :disabled="busy || index === columns.length - 1" :aria-label="`Переместить ${column.title} вправо`" @click="move(index, 1)">→</button>
          <button class="btn secondary" :disabled="busy" @click="edit(column)">Изменить</button>
          <button class="btn secondary" :disabled="busy" @click="column.is_archived ? archive(column) : archiveTarget = column">{{ column.is_archived ? 'Восстановить' : 'В архив' }}</button>
        </div>
      </li>
    </ol>
    <div v-if="archiveTarget" role="alert" class="archive-confirm">
      <p>Скрыть «{{ archiveTarget.title }}» у всех сотрудников? Значения останутся сохранены.</p>
      <button class="btn" :disabled="busy" @click="archive(archiveTarget)">Архивировать</button>
      <button class="btn secondary" :disabled="busy" @click="archiveTarget = null">Отмена</button>
    </div>
  </section>
</template>

<style scoped>
.columns-panel { padding: 1rem; margin: 1rem 0; }
.column-form, li, .actions { display: flex; flex-wrap: wrap; align-items: center; gap: .6rem; }
label { display: grid; gap: .25rem; }
li { justify-content: space-between; padding: .6rem 0; border-bottom: 1px solid var(--border); }
ol { padding-left: 0; list-style: none; }
.error { color: var(--danger); }
.archive-confirm { padding: .8rem; border: 1px solid var(--border); }
</style>
