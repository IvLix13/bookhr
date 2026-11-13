<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import DataTable from '@/components/DataTable.vue'
import type { ColumnDef } from '@/composables/useDataTable'
import type {
  PersonalDocumentErrorCode,
  PersonalDocumentErrorsCard,
  PersonalDocumentErrorsResult,
} from '@/types/personalDocumentErrors'
import { MODULE_LABELS } from '@/utils/labels'

const errorLabels: Record<PersonalDocumentErrorCode, string> = {
  grade: 'Ошибка в грейде',
  post: 'Ошибка в должности',
  contract: 'Ошибка в договоре',
  photo: 'Ошибка в фото',
  biography: 'Ошибка в биографии',
  attestation: 'Ошибка в аттестации',
  passport: 'Ошибка в паспорте',
}

const columns: ColumnDef<PersonalDocumentErrorsCard>[] = [
  { key: 'grade', label: 'Грейд', filterable: false },
  { key: 'full_name', label: 'ФИО', filterable: false },
  {
    key: 'error_count',
    label: 'Ошибки',
    filterable: false,
    getValue: (row) => row.errors.length,
  },
]

const result = ref<PersonalDocumentErrorsResult | null>(null)
const requestError = ref('')
const exporting = ref(false)
const exportError = ref('')
const lastSuccess = computed(() => {
  if (!result.value?.last_success_at) return null
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone: result.value.timezone,
  }).format(new Date(result.value.last_success_at))
})

onMounted(async () => {
  try {
    result.value = await api.refreshPersonalDocumentErrors()
  } catch (error) {
    requestError.value = normalizeError(error)
  }
})

async function downloadExcel() {
  if (exporting.value || !result.value?.items.length) return
  exporting.value = true
  exportError.value = ''
  try {
    await api.downloadPersonalDocumentErrors()
  } catch (error) {
    exportError.value = normalizeError(error)
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <section class="card errors-page">
    <header class="page-heading">
      <div>
        <h2>{{ MODULE_LABELS.personalDocumentErrors }}</h2>
        <p v-if="lastSuccess" class="muted">
          Последнее успешное обновление
          <time :datetime="result?.last_success_at ?? undefined">{{ lastSuccess }}</time>
        </p>
      </div>
      <button
        type="button"
        class="btn secondary"
        :disabled="exporting || !result?.items.length"
        @click="downloadExcel"
      >
        {{ exporting ? 'Скачивание…' : 'Выгрузка в Excel пофамильно' }}
      </button>
    </header>

    <p v-if="exportError" class="error-message" role="alert">{{ exportError }}</p>
    <p v-if="requestError" class="error-message" role="alert">{{ requestError }}</p>
    <p v-else-if="!result" role="status">Загружаем список ошибок…</p>
    <p v-else-if="result.state === 'not_configured'" role="status">Источник не настроен.</p>
    <p v-else-if="result.state === 'refreshing'" role="status">
      {{ lastSuccess
        ? 'Обновление ещё выполняется. Показан последний загруженный список.'
        : 'Обновление ещё выполняется. Откройте вкладку снова через несколько секунд.' }}
    </p>
    <p v-else-if="result.state === 'source_error'" class="error-message" role="alert">
      {{ lastSuccess
        ? 'Не удалось обновить список. Показан результат последней успешной загрузки.'
        : 'Не удалось загрузить список. Откройте вкладку снова, чтобы повторить попытку.' }}
    </p>
    <DataTable
      v-if="result && (result.state === 'ready' || result.last_success_at)"
      table-id="personal-document-errors"
      :columns="columns"
      :rows="result.items"
      row-key="ldnumber"
      empty-text="Ошибок не найдено."
    >
      <template #cell-error_count="{ row, display }">
        <div class="error-cell">
          <ul v-if="row.errors.length" class="error-list" role="list">
            <li v-for="code in row.errors" :key="code" class="error-label">
              {{ errorLabels[code] }}
            </li>
          </ul>
          <a
            class="btn secondary error-link"
            :href="row.personal_file_url"
            :aria-label="`Ошибок: ${display}. Открыть ЛД ${row.full_name || row.ldnumber} в новой вкладке`"
            target="_blank"
            rel="noopener noreferrer"
          >
            Ошибок: {{ display }} <span aria-hidden="true">↗</span>
          </a>
        </div>
      </template>
    </DataTable>
  </section>
</template>

<style scoped>
.errors-page {
  display: grid;
  gap: 1rem;
  min-width: 0;
  padding: 1rem;
}

.page-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.page-heading h2,
.errors-page p {
  margin: 0;
}

.page-heading .muted {
  margin-top: 0.35rem;
  color: var(--muted);
}

.error-message {
  color: var(--danger);
}

.error-cell {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.error-list {
  display: grid;
  justify-items: start;
  gap: 0.3rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.error-label {
  padding: 0.25rem 0.5rem;
  border: 1px solid #f4bcbc;
  border-radius: var(--radius-sm);
  background: #fdecec;
  color: #a12727;
  font-size: 0.875rem;
}

.error-link {
  display: inline-block;
  margin-inline-start: auto;
  white-space: nowrap;
}
</style>
