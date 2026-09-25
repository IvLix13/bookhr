<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import PageState from '@/components/PageState.vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import { useToast } from '@/composables/useToast'
import type { ColumnDef } from '@/composables/useDataTable'
import type { NextcloudUser, NotificationRule } from '@/types'
import { labelEventType } from '@/utils/labels'

const toast = useToast()

const rules = ref<NotificationRule[]>([])
const loading = ref(true)
const error = ref('')
const saving = ref(false)
const testing = ref(false)
const editing = ref<NotificationRule | null>(null)
const form = ref(emptyForm())
const testMessage = ref('Тестовое уведомление · Учет кадровых событий')
const recipientQuery = ref('')
const recipientResults = ref<NextcloudUser[]>([])
const recipientSearching = ref(false)
const recipientError = ref('')
const escalationQuery = ref('')
const escalationResults = ref<NextcloudUser[]>([])
const escalationSearching = ref(false)
const escalationError = ref('')

function emptyForm() {
  return {
    recipient_user_id: '',
    recipient_display_name: '',
    event_type: '',
    is_enabled: true,
    remind_days_before: 0,
    repeat_interval_days: 7,
    overdue_interval_days: 3,
    escalation_recipient_user_id: '',
    escalation_recipient_display_name: '',
    escalation_after_days: null as number | null,
    send_time_moscow: '09:00',
  }
}

const columns: ColumnDef<NotificationRule>[] = [
  {
    key: 'recipient',
    label: 'Получатель',
    getValue: (row) => row.recipient_display_name ?? row.recipient_user_id ?? 'Не выбран',
  },
  {
    key: 'event_type',
    label: 'Тип',
    getValue: (row) => row.event_type,
    format: (value) => (value ? labelEventType(value as string) : 'Все типы'),
  },
  {
    key: 'is_enabled',
    label: 'Статус',
    getValue: (row) => (row.is_enabled ? 'Включено' : 'Выключено'),
  },
  { key: 'repeat_interval_days', label: 'Повтор, дней' },
  { key: 'remind_days_before', label: 'Напомнить за, дней' },
  {
    key: 'escalation',
    label: 'Эскалация',
    getValue: (row) =>
      row.escalation_recipient_user_id
        ? `${row.escalation_after_days ?? '—'} дн. → ${row.escalation_recipient_display_name ?? row.escalation_recipient_user_id}`
        : '—',
  },
  { key: 'send_time_moscow', label: 'Время (МСК)' },
  {
    key: 'actions',
    label: '',
    sortable: false,
    filterable: false,
  },
]

async function loadRules() {
  loading.value = true
  error.value = ''
  try {
    rules.value = (await api.notificationRules()) as NotificationRule[]
  } catch (err) {
    error.value = normalizeError(err)
    rules.value = []
  } finally {
    loading.value = false
  }
}

onMounted(loadRules)

function startEdit(rule: NotificationRule) {
  editing.value = rule
  form.value = {
    recipient_user_id: rule.recipient_user_id ?? '',
    recipient_display_name: rule.recipient_display_name ?? '',
    event_type: rule.event_type ?? '',
    is_enabled: rule.is_enabled,
    remind_days_before: rule.remind_days_before,
    repeat_interval_days: rule.repeat_interval_days,
    overdue_interval_days: rule.overdue_interval_days,
    escalation_recipient_user_id: rule.escalation_recipient_user_id ?? '',
    escalation_recipient_display_name: rule.escalation_recipient_display_name ?? '',
    escalation_after_days: rule.escalation_after_days,
    send_time_moscow: rule.send_time_moscow,
  }
  recipientQuery.value = rule.recipient_display_name ?? rule.recipient_user_id ?? ''
  escalationQuery.value = rule.escalation_recipient_display_name ?? rule.escalation_recipient_user_id ?? ''
  recipientResults.value = []
  escalationResults.value = []
}

function resetForm() {
  editing.value = null
  form.value = emptyForm()
  recipientQuery.value = ''
  escalationQuery.value = ''
  recipientResults.value = []
  escalationResults.value = []
  recipientError.value = ''
  escalationError.value = ''
}

async function searchRecipients(kind: 'primary' | 'escalation') {
  const query = kind === 'primary' ? recipientQuery : escalationQuery
  const results = kind === 'primary' ? recipientResults : escalationResults
  const searching = kind === 'primary' ? recipientSearching : escalationSearching
  const searchError = kind === 'primary' ? recipientError : escalationError
  searchError.value = ''
  results.value = []
  if (query.value.trim().length < 2) {
    searchError.value = 'Введите минимум 2 символа ФИО'
    return
  }
  searching.value = true
  try {
    results.value = await api.searchNextcloudUsers(query.value.trim())
    if (!results.value.length) searchError.value = 'Пользователи не найдены'
  } catch (err) {
    searchError.value = normalizeError(err)
  } finally {
    searching.value = false
  }
}

function selectRecipient(kind: 'primary' | 'escalation', user: NextcloudUser) {
  if (kind === 'primary') {
    form.value.recipient_user_id = user.user_id
    form.value.recipient_display_name = user.display_name
    recipientQuery.value = user.display_name
    recipientResults.value = []
    recipientError.value = ''
  } else {
    form.value.escalation_recipient_user_id = user.user_id
    form.value.escalation_recipient_display_name = user.display_name
    escalationQuery.value = user.display_name
    escalationResults.value = []
    escalationError.value = ''
  }
}

function clearSelection(kind: 'primary' | 'escalation') {
  if (kind === 'primary') {
    form.value.recipient_user_id = ''
    form.value.recipient_display_name = ''
  } else {
    form.value.escalation_recipient_user_id = ''
    form.value.escalation_recipient_display_name = ''
  }
}

function clearEscalationRecipient() {
  escalationQuery.value = ''
  escalationResults.value = []
  escalationError.value = ''
  clearSelection('escalation')
}

async function saveRule() {
  saving.value = true
  error.value = ''
  try {
    const body = {
      ...form.value,
      event_type: form.value.event_type || null,
      escalation_recipient_user_id: form.value.escalation_recipient_user_id || null,
      escalation_recipient_display_name: form.value.escalation_recipient_display_name || null,
    }
    if (editing.value) {
      await api.updateNotificationRule(editing.value.id, body)
      toast.success('Правило обновлено')
    } else {
      await api.createNotificationRule(body)
      toast.success('Правило сохранено')
    }
    resetForm()
    await loadRules()
  } catch (err) {
    error.value = normalizeError(err)
    toast.error(error.value)
  } finally {
    saving.value = false
  }
}

async function toggleRule(rule: NotificationRule) {
  try {
    await api.updateNotificationRule(rule.id, { is_enabled: !rule.is_enabled })
    await loadRules()
    toast.success(rule.is_enabled ? 'Правило выключено' : 'Правило включено')
  } catch (err) {
    toast.error(normalizeError(err))
  }
}

async function testSend() {
  testing.value = true
  error.value = ''
  try {
    await api.testNotification({
      recipient_user_id: form.value.recipient_user_id,
      message: testMessage.value,
    })
    toast.success('Тестовое сообщение отправлено')
  } catch (err) {
    error.value = normalizeError(err)
    toast.error(error.value)
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <section class="tab-page">
    <header class="tab-header">
      <div>
        <h3>Настройки уведомлений Nextcloud</h3>
        <p class="hint">
          Найдите получателя по ФИО и выберите его из Nextcloud. Сообщения будут
          отправляться в личный диалог Talk от имени сервисного пользователя.
        </p>
      </div>
    </header>

    <form class="form card" @submit.prevent="saveRule">
      <h4>{{ editing ? 'Редактировать правило' : 'Новое правило' }}</h4>
      <div class="recipient-picker">
        <label>
          Получатель в Nextcloud
          <span class="search-row">
            <input
              v-model="recipientQuery"
              placeholder="Введите ФИО"
              @input="clearSelection('primary')"
              @keydown.enter.prevent="searchRecipients('primary')"
            />
            <button class="btn secondary" type="button" :disabled="recipientSearching" @click="searchRecipients('primary')">
              {{ recipientSearching ? 'Поиск...' : 'Найти' }}
            </button>
          </span>
        </label>
        <p v-if="form.recipient_user_id" class="selected-recipient">
          Выбран: {{ form.recipient_display_name }} ({{ form.recipient_user_id }})
        </p>
        <p v-if="recipientError" class="error">{{ recipientError }}</p>
        <div v-if="recipientResults.length" class="search-results" role="listbox" aria-label="Пользователи Nextcloud">
          <button
            v-for="user in recipientResults"
            :key="user.user_id"
            type="button"
            role="option"
            @click="selectRecipient('primary', user)"
          >
            <strong>{{ user.display_name }}</strong>
            <small>{{ user.user_id }}</small>
          </button>
        </div>
      </div>
      <label>
        Тип события
        <input v-model="form.event_type" placeholder="contract / grade / ..." />
      </label>
      <label class="checkbox">
        <input v-model="form.is_enabled" type="checkbox" />
        Правило включено
      </label>
      <label>Напомнить за, дней<input v-model.number="form.remind_days_before" type="number" min="0" /></label>
      <label>Повтор, дней<input v-model.number="form.repeat_interval_days" type="number" min="1" /></label>
      <label>Просрочка, дней<input v-model.number="form.overdue_interval_days" type="number" min="1" /></label>
      <div class="recipient-picker">
        <label>
          Получатель эскалации
          <span class="search-row">
            <input
              v-model="escalationQuery"
              placeholder="Введите ФИО (опционально)"
              @input="clearSelection('escalation')"
              @keydown.enter.prevent="searchRecipients('escalation')"
            />
            <button class="btn secondary" type="button" :disabled="escalationSearching" @click="searchRecipients('escalation')">
              {{ escalationSearching ? 'Поиск...' : 'Найти' }}
            </button>
            <button v-if="escalationQuery" class="btn ghost" type="button" @click="clearEscalationRecipient">Очистить</button>
          </span>
        </label>
        <p v-if="form.escalation_recipient_user_id" class="selected-recipient">
          Выбран: {{ form.escalation_recipient_display_name }} ({{ form.escalation_recipient_user_id }})
        </p>
        <p v-if="escalationError" class="error">{{ escalationError }}</p>
        <div v-if="escalationResults.length" class="search-results" role="listbox" aria-label="Пользователи Nextcloud для эскалации">
          <button
            v-for="user in escalationResults"
            :key="user.user_id"
            type="button"
            role="option"
            @click="selectRecipient('escalation', user)"
          >
            <strong>{{ user.display_name }}</strong>
            <small>{{ user.user_id }}</small>
          </button>
        </div>
      </div>
      <label>
        Эскалация после, дней
        <input
          v-model.number="form.escalation_after_days"
          type="number"
          min="1"
          placeholder="например 7"
        />
      </label>
      <label>Время (МСК)<input v-model="form.send_time_moscow" /></label>
      <div class="actions">
        <button class="btn" type="submit" :disabled="saving || !form.recipient_user_id">
          {{ saving ? 'Сохранение...' : editing ? 'Сохранить изменения' : 'Сохранить правило' }}
        </button>
        <button v-if="editing" class="btn secondary" type="button" @click="resetForm">Отмена</button>
      </div>
    </form>

    <div class="test-block card">
      <label>Тестовое сообщение<input v-model="testMessage" /></label>
      <button class="btn secondary" type="button" :disabled="testing || !form.recipient_user_id" @click="testSend">
        {{ testing ? 'Отправка...' : 'Отправить тест' }}
      </button>
    </div>

    <PageState :loading="loading" :error="error" @retry="loadRules()">
      <DataTable
        :columns="columns"
        :rows="rules"
        row-key="id"
        search-placeholder="Поиск по правилам..."
      >
        <template #cell-actions="{ row }">
          <div class="row-actions">
            <button class="btn secondary" type="button" @click="startEdit(row)">Изменить</button>
            <button class="btn ghost" type="button" @click="toggleRule(row)">
              {{ row.is_enabled ? 'Выключить' : 'Включить' }}
            </button>
          </div>
        </template>
      </DataTable>
    </PageState>
  </section>
</template>

<style scoped>
.tab-page {
  display: grid;
  gap: 1rem;
}

.tab-header h3 {
  margin: 0;
}

.hint {
  margin: 0.35rem 0 0;
  color: var(--muted);
  max-width: 42rem;
}

.form,
.test-block {
  padding: 1rem;
  display: grid;
  gap: 0.75rem;
}

.form h4 {
  margin: 0;
}

label {
  display: grid;
  gap: 0.35rem;
}

label.checkbox {
  grid-auto-flow: column;
  justify-content: start;
  align-items: center;
  gap: 0.5rem;
}

input {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.75rem 0.9rem;
}

.recipient-picker {
  display: grid;
  gap: 0.4rem;
}

.search-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.search-row input {
  flex: 1 1 18rem;
}

.search-results {
  display: grid;
  gap: 0.35rem;
  padding: 0.35rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  max-height: 16rem;
  overflow-y: auto;
}

.search-results button {
  display: grid;
  gap: 0.2rem;
  padding: 0.65rem 0.75rem;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.search-results button:hover {
  background: var(--surface-hover, rgba(15, 23, 42, 0.06));
}

.search-results small,
.selected-recipient {
  color: var(--muted);
}

.selected-recipient,
.error {
  margin: 0;
}

.actions,
.row-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}
</style>
