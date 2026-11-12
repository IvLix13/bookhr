<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import DataTable from '@/components/DataTable.vue'
import type { ColumnDef } from '@/composables/useDataTable'
import type {
  PersonalDocumentErrorsCard,
  PersonalDocumentErrorsResult,
} from '@/types/personalDocumentErrors'
import { MODULE_LABELS } from '@/utils/labels'

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
</script>

<template>
  <section class="card errors-page">
    <header class="page-heading">
      <h2>{{ MODULE_LABELS.personalDocumentErrors }}</h2>
      <p v-if="lastSuccess" class="muted">
        Последнее успешное обновление
        <time :datetime="result?.last_success_at ?? undefined">{{ lastSuccess }}</time>
      </p>
    </header>

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
        <a
          class="btn secondary error-link"
          :href="row.personal_file_url"
          :aria-label="`Ошибок: ${display}. Открыть ЛД ${row.full_name || row.ldnumber} в новой вкладке`"
          target="_blank"
          rel="noopener noreferrer"
        >
          Ошибок: {{ display }} <span aria-hidden="true">↗</span>
        </a>
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
  align-items: baseline;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.page-heading h2,
.errors-page p {
  margin: 0;
}

.muted {
  color: var(--muted);
}

.error-message {
  color: var(--danger);
}

.error-link {
  display: inline-block;
  white-space: nowrap;
}
</style>
