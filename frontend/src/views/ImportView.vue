<script setup lang="ts">
import { ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import { api } from '@/api/client'
import type { ColumnDef } from '@/composables/useDataTable'
import type { ImportJob, ImportRow } from '@/types'

const file = ref<File | null>(null)
const job = ref<ImportJob | null>(null)
const message = ref('')
const error = ref('')
const downloading = ref(false)

const importColumns: ColumnDef<ImportRow>[] = [
  { key: 'row_number', label: 'Строка' },
  { key: 'action', label: 'Действие', getValue: (row) => row.action ?? '—' },
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
    message.value = 'Шаблон скачан'
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Не удалось скачать шаблон'
  } finally {
    downloading.value = false
  }
}

async function upload() {
  if (!file.value) return
  message.value = ''
  error.value = ''
  job.value = (await api.uploadImport(file.value)) as ImportJob
}

async function confirm() {
  if (!job.value) return
  job.value = (await api.confirmImport(job.value.id, {})) as ImportJob
  message.value = 'Импорт подтверждён'
}
</script>

<template>
  <section class="card page">
    <header><h2>Импорт из Excel</h2></header>
    <div class="actions">
      <button class="btn secondary" type="button" :disabled="downloading" @click="downloadTemplate">
        {{ downloading ? 'Скачивание...' : 'Скачать шаблон Excel' }}
      </button>
      <input type="file" accept=".xlsx" @change="(e) => file = (e.target as HTMLInputElement).files?.[0] ?? null" />
      <button class="btn" :disabled="!file" @click="upload">Проверить файл</button>
      <button class="btn secondary" :disabled="!job || job.status !== 'validated'" @click="confirm">
        Подтвердить импорт
      </button>
    </div>
    <p v-if="message">{{ message }}</p>
    <p v-if="error" class="error">{{ error }}</p>
    <div v-if="job" class="summary">
      <p>Файл: {{ job.filename }}</p>
      <p>Статус: {{ job.status }}</p>
      <pre>{{ job.summary }}</pre>
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

.error {
  color: var(--danger);
  margin: 0;
}
</style>
