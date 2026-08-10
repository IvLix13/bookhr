<script setup lang="ts">
import { computed, ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import ImportDropzone from '@/components/ImportDropzone.vue'
import ImportSummary from '@/components/ImportSummary.vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import { useToast } from '@/composables/useToast'
import type { ColumnDef } from '@/composables/useDataTable'
import type { ImportJob, ImportRow } from '@/types'
import { labelImportAction, labelImportStatus } from '@/utils/labels'

const toast = useToast()

const file = ref<File | null>(null)
const job = ref<ImportJob | null>(null)
const error = ref('')
const downloading = ref(false)
const uploading = ref(false)
const confirming = ref(false)

const hasRowErrors = computed(() =>
  job.value?.rows.some((row) => row.errors?.length) ?? false,
)

const importColumns: ColumnDef<ImportRow>[] = [
  { key: 'row_number', label: 'Строка' },
  {
    key: 'action',
    label: 'Действие',
    getValue: (row) => row.action,
    format: (value) => labelImportAction(value as string | null),
  },
  { key: 'person_uuid', label: 'UUID', getValue: (row) => row.person_uuid ?? '—' },
  {
    key: 'details',
    label: 'Ошибки',
    getValue: (row) => row.errors?.join(', ') ?? row.warnings?.join(', ') ?? '—',
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
}

async function upload() {
  if (!file.value) return
  uploading.value = true
  error.value = ''
  try {
    job.value = (await api.uploadImport(file.value)) as ImportJob
    toast.success('Файл проверен')
  } catch (err) {
    error.value = normalizeError(err)
    toast.error(error.value)
  } finally {
    uploading.value = false
  }
}

async function confirm() {
  if (!job.value || hasRowErrors.value) return
  confirming.value = true
  error.value = ''
  try {
    job.value = (await api.confirmImport(job.value.id, {})) as ImportJob
    toast.success('Импорт подтверждён')
  } catch (err) {
    error.value = normalizeError(err)
    toast.error(error.value)
  } finally {
    confirming.value = false
  }
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
      <p v-if="hasRowErrors" class="error">
        Исправьте ошибки в файле перед подтверждением импорта.
      </p>
      <button
        class="btn secondary"
        type="button"
        :disabled="!job || job.status !== 'validated' || hasRowErrors || confirming"
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
</style>
