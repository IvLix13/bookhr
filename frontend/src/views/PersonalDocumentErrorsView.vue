<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import OnboardingDialog from '@/components/OnboardingDialog.vue'
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

const result = ref<PersonalDocumentErrorsResult | null>(null)
const selected = ref<PersonalDocumentErrorsCard | null>(null)
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
    <p v-if="lastSuccess && !result?.items.length" role="status">Ошибок не найдено.</p>

    <div v-if="result?.items.length" class="error-cards" aria-label="Сотрудники с ошибками в личных делах">
      <button
        v-for="card in result.items"
        :key="card.ldnumber"
        class="error-card"
        type="button"
        aria-haspopup="dialog"
        @click="selected = card"
      >
        <span class="identity">
          <span class="muted">{{ card.grade || 'Грейд не указан' }}</span>
          <strong class="employee-name">{{ card.full_name || 'ФИО не указано' }}</strong>
          <span class="muted">ЛД № {{ card.ldnumber }}</span>
        </span>
        <span class="card-actions">
          <span class="badge danger">Ошибок: {{ card.errors.length }}</span>
          <span class="btn secondary">Открыть ошибки</span>
        </span>
      </button>
    </div>

    <OnboardingDialog
      v-if="selected"
      title="Ошибки в личных документах"
      @close="selected = null"
    >
      <div class="employee-details">
        <h3 class="employee-name">{{ selected.full_name || 'ФИО не указано' }}</h3>
        <dl>
          <div><dt>Грейд</dt><dd>{{ selected.grade || '—' }}</dd></div>
          <div><dt>Номер ЛД</dt><dd>{{ selected.ldnumber }}</dd></div>
          <div><dt>Номер карточки</dt><dd>{{ selected.cardnumber || '—' }}</dd></div>
        </dl>
      </div>
      <table class="table error-table">
        <thead>
          <tr>
            <th scope="col">Вид ошибки</th>
            <th scope="col">Внешнее приложение</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="code in selected.errors" :key="code">
            <td>{{ errorLabels[code] }}</td>
            <td>
              <a
                :href="selected.personal_file_url"
                :aria-label="`Открыть ЛД: ${errorLabels[code]} (новая вкладка)`"
                target="_blank"
                rel="noopener noreferrer"
              >Открыть ЛД ↗</a>
            </td>
          </tr>
        </tbody>
      </table>
    </OnboardingDialog>
  </section>
</template>

<style scoped>
.errors-page { padding: 1.25rem; min-width: 0; }
.page-heading { display: flex; justify-content: space-between; align-items: baseline; gap: .75rem; flex-wrap: wrap; margin-bottom: 1rem; }
.page-heading h2, .page-heading p { margin: 0; }
.muted { color: var(--muted); }
.error-message { color: var(--danger); }
.error-cards { display: grid; gap: 1rem; }
.error-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.25rem;
  width: 100%;
  padding: 1.4rem 1.5rem;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: var(--surface);
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.error-card:hover { background: var(--bg); }
.error-card:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.identity { display: grid; gap: .35rem; min-width: 0; overflow-wrap: anywhere; }
.employee-name { margin: 0; font-size: clamp(1.25rem, 1.6vw, 1.9rem); line-height: 1.3; overflow-wrap: anywhere; }
.card-actions { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.employee-details { padding: 1rem; border: 1px solid var(--border); border-radius: 12px; background: var(--bg); }
.employee-details dl { display: flex; flex-wrap: wrap; gap: .75rem 2rem; margin: .75rem 0 0; }
.employee-details dl > div { min-width: 0; }
.employee-details dt { color: var(--muted); font-size: .875rem; }
.employee-details dd { margin: .25rem 0 0; overflow-wrap: anywhere; }
.error-table { margin-top: 1rem; }
.error-table a { color: var(--accent); }

@media (max-width: 640px) {
  .errors-page { padding: .8rem; }
  .error-card { flex-direction: column; align-items: flex-start; padding: 1rem; }
}
</style>
