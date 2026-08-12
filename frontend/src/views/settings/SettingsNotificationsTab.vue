<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import PageState from '@/components/PageState.vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import { useToast } from '@/composables/useToast'
import type { ColumnDef } from '@/composables/useDataTable'
import type { NotificationRule } from '@/types'
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

function emptyForm() {
  return {
    room_token: '',
    room_name: '',
    event_type: '',
    is_enabled: true,
    remind_days_before: 0,
    repeat_interval_days: 7,
    overdue_interval_days: 3,
    escalation_room_token: '',
    escalation_after_days: null as number | null,
    send_time_moscow: '09:00',
  }
}

const columns: ColumnDef<NotificationRule>[] = [
  {
    key: 'room',
    label: 'Комната',
    getValue: (row) => row.room_name ?? row.room_token,
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
      row.escalation_room_token
        ? `${row.escalation_after_days ?? '—'} дн. → ${row.escalation_room_token}`
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
    room_token: rule.room_token,
    room_name: rule.room_name ?? '',
    event_type: rule.event_type ?? '',
    is_enabled: rule.is_enabled,
    remind_days_before: rule.remind_days_before,
    repeat_interval_days: rule.repeat_interval_days,
    overdue_interval_days: rule.overdue_interval_days,
    escalation_room_token: rule.escalation_room_token ?? '',
    escalation_after_days: rule.escalation_after_days,
    send_time_moscow: rule.send_time_moscow,
  }
}

function resetForm() {
  editing.value = null
  form.value = emptyForm()
}

async function saveRule() {
  saving.value = true
  error.value = ''
  try {
    const body = {
      ...form.value,
      event_type: form.value.event_type || null,
      escalation_room_token: form.value.escalation_room_token || null,
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
      room_token: form.value.room_token,
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
        <h3>Настройки бота</h3>
        <p class="hint">
          Правила уведомлений Nextcloud Talk и тестовая отправка. URL и токен бота
          настраиваются администратором сервера через переменные окружения.
        </p>
      </div>
    </header>

    <form class="form card" @submit.prevent="saveRule">
      <h4>{{ editing ? 'Редактировать правило' : 'Новое правило' }}</h4>
      <label>Токен комнаты<input v-model="form.room_token" required /></label>
      <label>Название комнаты<input v-model="form.room_name" /></label>
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
      <label>Токен комнаты эскалации<input v-model="form.escalation_room_token" placeholder="опционально" /></label>
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
        <button class="btn" type="submit" :disabled="saving">
          {{ saving ? 'Сохранение...' : editing ? 'Сохранить изменения' : 'Сохранить правило' }}
        </button>
        <button v-if="editing" class="btn secondary" type="button" @click="resetForm">Отмена</button>
      </div>
    </form>

    <div class="test-block card">
      <label>Тестовое сообщение<input v-model="testMessage" /></label>
      <button class="btn secondary" type="button" :disabled="testing || !form.room_token" @click="testSend">
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

.actions,
.row-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}
</style>
