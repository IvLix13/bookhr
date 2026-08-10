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
const form = ref({
  room_token: '',
  room_name: '',
  event_type: '',
  repeat_interval_days: 7,
  overdue_interval_days: 3,
  send_time_moscow: '09:00',
})
const testMessage = ref('Тестовое уведомление Bookuchet')

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
  { key: 'repeat_interval_days', label: 'Повтор, дней' },
  { key: 'send_time_moscow', label: 'Время (МСК)' },
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

async function createRule() {
  saving.value = true
  error.value = ''
  try {
    await api.createNotificationRule(form.value)
    toast.success('Правило сохранено')
    await loadRules()
  } catch (err) {
    error.value = normalizeError(err)
    toast.error(error.value)
  } finally {
    saving.value = false
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
  <section class="card page">
    <header><h2>Настройки Nextcloud Talk</h2></header>

    <form class="form" @submit.prevent="createRule">
      <label>Токен комнаты<input v-model="form.room_token" required /></label>
      <label>Название комнаты<input v-model="form.room_name" /></label>
      <label>
        Тип события
        <input v-model="form.event_type" placeholder="contract / grade / ..." />
      </label>
      <label>Повтор, дней<input v-model.number="form.repeat_interval_days" type="number" min="1" /></label>
      <label>Просрочка, дней<input v-model.number="form.overdue_interval_days" type="number" min="1" /></label>
      <label>Время (МСК)<input v-model="form.send_time_moscow" /></label>
      <button class="btn" type="submit" :disabled="saving">
        {{ saving ? 'Сохранение...' : 'Сохранить правило' }}
      </button>
    </form>

    <div class="test-block">
      <label>Тестовое сообщение<input v-model="testMessage" /></label>
      <button class="btn secondary" type="button" :disabled="testing || !form.room_token" @click="testSend">
        {{ testing ? 'Отправка...' : 'Отправить тест' }}
      </button>
    </div>

    <PageState
      :loading="loading"
      :error="error"
      @retry="loadRules()"
    >
      <DataTable
        :columns="columns"
        :rows="rules"
        row-key="id"
        search-placeholder="Поиск по правилам..."
      />
    </PageState>
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
  display: grid;
  gap: 1rem;
}

.form,
.test-block {
  display: grid;
  gap: 0.75rem;
  max-width: 520px;
}

label {
  display: grid;
  gap: 0.35rem;
}

input {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.75rem 0.9rem;
}
</style>
