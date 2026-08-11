<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import ImportDropzone from '@/components/ImportDropzone.vue'
import ImportSummary from '@/components/ImportSummary.vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import { useToast } from '@/composables/useToast'
import type { ColumnDef } from '@/composables/useDataTable'
import type { ImportJob, ImportRow } from '@/types'
import {
  labelImportAction,
  labelImportResult,
  labelImportStatus,
} from '@/utils/labels'

const toast = useToast()

const file = ref<File | null>(null)
const job = ref<ImportJob | null>(null)
const error = ref('')
const downloading = ref(false)
const uploading = ref(false)
const confirming = ref(false)

/** row id -> action value: create | skip | update:<uuid> */
const rowActions = reactive<Record<number, string>>({})

const hasRowErrors = computed(() =>
  job.value?.rows.some((row) => row.errors?.length) ?? false,
)

const ambiguousRows = computed(
  () => job.value?.rows.filter((row) => row.action === 'ambiguous') ?? [],
)

const unresolvedAmbiguous = computed(() =>
  ambiguousRows.value.some((row) => !rowActions[row.id]),
)

const canConfirm = computed(
  () =>
    !!job.value
    && job.value.status === 'validated'
    && !hasRowErrors.value
    && !unresolvedAmbiguous.value
    && !confirming.value,
)

const importColumns: ColumnDef<ImportRow>[] = [
  { key: 'row_number', label: 'Строка' },
  {
    key: 'full_name',
    label: 'ФИО',
    getValue: (row) => row.full_name ?? '—',
  },
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
]

async function downloadTemplate() {
  downloading.value = true
  error.value = ''
  try {
    await api.downloadImportTemplate()
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
  for (const key of Object.keys(rowActions)) {
    delete rowActions[Number(key)]
  }
}

async function upload() {
  if (!file.value) return
  uploading.value = true
  error.value = ''
  try {
    job.value = (await api.uploadImport(file.value)) as ImportJob
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
</script>

<template>
  <section class="card page">
    <header><h2>Импорт из Excel</h2></header>
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
        <p class="hint">
          Найдено несколько сотрудников с одинаковым ФИО. Для каждой строки укажите,
          создать нового, обновить существующего или пропустить.
        </p>
        <ul class="ambiguous-list">
          <li v-for="row in ambiguousRows" :key="row.id" class="ambiguous-item">
            <div class="ambiguous-main">
              <strong>Строка {{ row.row_number }}</strong>
              <span>{{ row.full_name ?? '—' }}</span>
            </div>
            <label class="ambiguous-select">
              Действие
              <select v-model="rowActions[row.id]" required>
                <option disabled value="">Выберите…</option>
                <option value="create">Создать нового</option>
                <option value="skip">Пропустить</option>
                <option
                  v-for="candidate in row.candidates ?? []"
                  :key="candidate.uuid"
                  :value="`update:${candidate.uuid}`"
                >
                  Обновить: {{ candidateLabel(candidate) }}
                </option>
              </select>
            </label>
          </li>
        </ul>
      </section>

      <p v-if="hasRowErrors" class="error">
        Исправьте ошибки в файле перед подтверждением импорта.
      </p>
      <p v-else-if="unresolvedAmbiguous" class="error">
        Разрешите все дубликаты перед подтверждением импорта.
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
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
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
</style>
