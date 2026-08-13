<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import DataTable from '@/components/DataTable.vue'
import GradeCreateModal from '@/components/GradeCreateModal.vue'
import ImportDropzone from '@/components/ImportDropzone.vue'
import ImportSummary from '@/components/ImportSummary.vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import { useToast } from '@/composables/useToast'
import type { ColumnDef } from '@/composables/useDataTable'
import { useAuthStore } from '@/stores/auth'
import type { ImportJob, ImportRow, ImportType, UnknownGrade } from '@/types'
import {
  labelImportAction,
  labelImportResult,
  labelImportStatus,
} from '@/utils/labels'

const props = defineProps<{
  importType: ImportType
}>()

const auth = useAuthStore()
const toast = useToast()

const file = ref<File | null>(null)
const job = ref<ImportJob | null>(null)
const error = ref('')
const downloading = ref(false)
const uploading = ref(false)
const confirming = ref(false)
const revalidating = ref(false)
const modalGradeName = ref<string | null>(null)

/** row id -> action value: create | skip | update:<uuid> */
const rowActions = reactive<Record<number, string>>({})
/** normalized grade name -> skipped */
const gradeSkips = reactive<Record<string, boolean>>({})

const isRewards = computed(() => props.importType === 'rewards')

const hasRowErrors = computed(() =>
  job.value?.rows.some((row) => row.errors?.length) ?? false,
)

const ambiguousRows = computed(
  () => job.value?.rows.filter((row) => row.action === 'ambiguous') ?? [],
)

const unresolvedAmbiguous = computed(() =>
  ambiguousRows.value.some((row) => !rowActions[row.id]),
)

const unknownGrades = computed<UnknownGrade[]>(() => job.value?.unknown_grades ?? [])

const unresolvedGrades = computed(() =>
  unknownGrades.value.some((grade) => !gradeSkips[gradeKey(grade.name)]),
)

const canConfirm = computed(
  () =>
    !!job.value
    && job.value.status === 'validated'
    && !hasRowErrors.value
    && !unresolvedAmbiguous.value
    && !unresolvedGrades.value
    && !confirming.value
    && !revalidating.value,
)

const importColumns = computed<ColumnDef<ImportRow>[]>(() => {
  const columns: ColumnDef<ImportRow>[] = [
    { key: 'row_number', label: 'Строка' },
    {
      key: 'full_name',
      label: 'ФИО',
      getValue: (row) => row.full_name ?? '—',
    },
  ]
  if (isRewards.value) {
    columns.push({
      key: 'reward_type',
      label: 'Вид поощрения',
      getValue: (row) => row.reward_type ?? '—',
    })
  }
  columns.push(
    {
      key: 'action',
      label: 'Действие',
      getValue: (row) => row.action,
      format: (value) => labelImportAction(value as string | null),
    },
    {
      key: 'result',
      label: 'Итог',
      getValue: (row) => row.result ?? null,
      format: (value) => labelImportResult(value as string | null),
    },
    {
      key: 'details',
      label: 'Детали',
      getValue: (row) =>
        row.result_message
        ?? row.errors?.join(', ')
        ?? row.warnings?.join(', ')
        ?? '—',
    },
  )
  return columns
})

function gradeKey(name: string): string {
  return name.trim().toLowerCase()
}

function clearGradeSkips() {
  for (const key of Object.keys(gradeSkips)) {
    delete gradeSkips[key]
  }
}

function pruneGradeSkips() {
  const remaining = new Set(unknownGrades.value.map((grade) => gradeKey(grade.name)))
  for (const key of Object.keys(gradeSkips)) {
    if (!remaining.has(key)) {
      delete gradeSkips[key]
    }
  }
}

function resetState() {
  file.value = null
  job.value = null
  error.value = ''
  modalGradeName.value = null
  clearGradeSkips()
  for (const key of Object.keys(rowActions)) {
    delete rowActions[Number(key)]
  }
}

watch(
  () => props.importType,
  () => {
    resetState()
  },
)

async function downloadTemplate() {
  downloading.value = true
  error.value = ''
  try {
    await api.downloadImportTemplate(1, props.importType)
    toast.success('Шаблон скачан')
  } catch (err) {
    error.value = normalizeError(err)
    toast.error(error.value)
  } finally {
    downloading.value = false
  }
}

function onFileSelect(selected: File) {
  file.value = selected
  job.value = null
  error.value = ''
  modalGradeName.value = null
  clearGradeSkips()
  for (const key of Object.keys(rowActions)) {
    delete rowActions[Number(key)]
  }
}

async function upload() {
  if (!file.value) return
  uploading.value = true
  error.value = ''
  try {
    job.value = (await api.uploadImport(file.value, props.importType)) as ImportJob
    clearGradeSkips()
    for (const key of Object.keys(rowActions)) {
      delete rowActions[Number(key)]
    }
    toast.success('Файл проверен')
  } catch (err) {
    error.value = normalizeError(err)
    toast.error(error.value)
  } finally {
    uploading.value = false
  }
}

async function confirm() {
  if (!job.value || !canConfirm.value) return
  confirming.value = true
  error.value = ''
  try {
    const payload: Record<number, string> = {}
    for (const [key, value] of Object.entries(rowActions)) {
      if (value) payload[Number(key)] = value
    }
    job.value = (await api.confirmImport(job.value.id, payload)) as ImportJob
    toast.success('Импорт подтверждён')
  } catch (err) {
    error.value = normalizeError(err)
    toast.error(error.value)
  } finally {
    confirming.value = false
  }
}

function candidateLabel(candidate: { full_name: string | null; title?: string | null }): string {
  const name = candidate.full_name ?? 'Без имени'
  return candidate.title ? `${name} — ${candidate.title}` : name
}

function ambiguousHint(): string {
  if (isRewards.value) {
    return 'Найдено несколько сотрудников с одинаковым ФИО. Для каждой строки выберите сотрудника или пропустите.'
  }
  return 'Найдено несколько сотрудников с одинаковым ФИО. Для каждой строки укажите, создать нового, обновить существующего или пропустить.'
}

function skipGrade(name: string) {
  gradeSkips[gradeKey(name)] = true
}

function openGradeModal(name: string) {
  modalGradeName.value = name
}

function closeGradeModal() {
  modalGradeName.value = null
}

async function onGradeCreated() {
  if (!job.value) {
    closeGradeModal()
    return
  }
  revalidating.value = true
  error.value = ''
  try {
    job.value = (await api.revalidateImport(job.value.id)) as ImportJob
    pruneGradeSkips()
    closeGradeModal()
    toast.success('Грейд добавлен')
  } catch (err) {
    error.value = normalizeError(err)
    toast.error(error.value)
  } finally {
    revalidating.value = false
  }
}

function unknownGradeHint(): string {
  if (auth.canEdit()) {
    return 'Грейды из файла, которых нет в справочнике. Заведите их или пропустите — иначе импорт нельзя подтвердить.'
  }
  return 'Грейды из файла, которых нет в справочнике. Завести грейд может администратор или HR. Пропустите грейд, чтобы импортировать сотрудников без него.'
}

function gradeStatus(name: string): string {
  return gradeSkips[gradeKey(name)] ? 'Будет пропущен' : 'Ожидает решения'
}

function rowsLabel(count: number): string {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return `${count} строка`
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${count} строки`
  return `${count} строк`
}
</script>

<template>
  <div class="workflow">
    <div class="actions">
      <button class="btn secondary" type="button" :disabled="downloading" @click="downloadTemplate">
        {{ downloading ? 'Скачивание...' : 'Скачать шаблон Excel' }}
      </button>
    </div>

    <ImportDropzone
      :disabled="uploading || confirming"
      @select="onFileSelect"
    />

    <div v-if="file" class="file-info">
      <span>Выбран файл: {{ file.name }}</span>
      <button class="btn" type="button" :disabled="uploading" @click="upload">
        {{ uploading ? 'Проверка...' : 'Проверить файл' }}
      </button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="job" class="summary">
      <ImportSummary :job="job" />

      <section v-if="ambiguousRows.length && job.status === 'validated'" class="ambiguous">
        <h3>Дубликаты — выберите действие</h3>
        <p class="hint">{{ ambiguousHint() }}</p>
        <ul class="ambiguous-list">
          <li v-for="row in ambiguousRows" :key="row.id" class="ambiguous-item">
            <div class="ambiguous-main">
              <strong>Строка {{ row.row_number }}</strong>
              <span>{{ row.full_name ?? '—' }}</span>
              <span v-if="row.reward_type" class="meta">{{ row.reward_type }}</span>
            </div>
            <label class="ambiguous-select">
              Действие
              <select v-model="rowActions[row.id]" required>
                <option disabled value="">Выберите…</option>
                <option v-if="!isRewards" value="create">Создать нового</option>
                <option value="skip">Пропустить</option>
                <option
                  v-for="candidate in row.candidates ?? []"
                  :key="candidate.uuid"
                  :value="`update:${candidate.uuid}`"
                >
                  {{ isRewards ? 'Выбрать' : 'Обновить' }}: {{ candidateLabel(candidate) }}
                </option>
              </select>
            </label>
          </li>
        </ul>
      </section>

      <section v-if="unknownGrades.length && job.status === 'validated'" class="unknown-grades">
        <h3>Неизвестные грейды</h3>
        <p class="hint">{{ unknownGradeHint() }}</p>
        <ul class="unknown-list">
          <li v-for="grade in unknownGrades" :key="gradeKey(grade.name)" class="unknown-item">
            <div class="unknown-main">
              <strong>{{ grade.name }}</strong>
              <span class="meta">{{ rowsLabel(grade.count) }}</span>
              <span class="meta">{{ gradeStatus(grade.name) }}</span>
            </div>
            <div class="unknown-actions">
              <button
                v-if="auth.canEdit()"
                class="btn"
                type="button"
                :disabled="revalidating"
                @click="openGradeModal(grade.name)"
              >
                Завести в справочнике
              </button>
              <button
                class="btn secondary"
                type="button"
                :disabled="Boolean(gradeSkips[gradeKey(grade.name)])"
                @click="skipGrade(grade.name)"
              >
                Пропустить
              </button>
            </div>
          </li>
        </ul>
      </section>

      <p v-if="hasRowErrors" class="error">
        Исправьте ошибки в файле перед подтверждением импорта.
      </p>
      <p v-else-if="unresolvedAmbiguous" class="error">
        Разрешите все дубликаты перед подтверждением импорта.
      </p>
      <p v-else-if="unresolvedGrades" class="error">
        Разрешите неизвестные грейды перед подтверждением импорта.
      </p>
      <button
        class="btn secondary"
        type="button"
        :disabled="!canConfirm"
        @click="confirm"
      >
        {{ confirming ? 'Подтверждение...' : 'Подтвердить импорт' }}
      </button>
      <p class="status-note">Статус: {{ labelImportStatus(job.status) }}</p>
      <DataTable
        :columns="importColumns"
        :rows="job.rows"
        row-key="id"
        search-placeholder="Поиск по результатам проверки..."
      />
    </div>

    <GradeCreateModal
      :open="modalGradeName !== null"
      :initial-name="modalGradeName ?? ''"
      @close="closeGradeModal"
      @saved="onGradeCreated"
    />
  </div>
</template>

<style scoped>
.workflow {
  display: grid;
  gap: 1rem;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}

.file-info {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}

.summary {
  display: grid;
  gap: 1rem;
}

.status-note {
  margin: 0;
  color: var(--muted);
}

.error {
  color: var(--danger);
  margin: 0;
}

.meta {
  color: var(--muted);
  font-size: 0.9rem;
}

.ambiguous {
  display: grid;
  gap: 0.75rem;
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.ambiguous h3 {
  margin: 0;
  font-size: 1rem;
}

.hint {
  margin: 0;
  color: var(--muted);
  font-size: 0.9rem;
}

.ambiguous-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.75rem;
}

.ambiguous-item {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: center;
}

.ambiguous-main {
  display: grid;
  gap: 0.2rem;
}

.ambiguous-select {
  display: grid;
  gap: 0.35rem;
  min-width: min(320px, 100%);
}

.ambiguous-select select {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.55rem 0.75rem;
  background: var(--surface);
}

.unknown-grades {
  display: grid;
  gap: 0.75rem;
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.unknown-grades h3 {
  margin: 0;
  font-size: 1rem;
}

.unknown-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.75rem;
}

.unknown-item {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: center;
}

.unknown-main {
  display: grid;
  gap: 0.2rem;
}

.unknown-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
</style>
