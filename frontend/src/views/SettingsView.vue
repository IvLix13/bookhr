<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import { api } from '@/api/client'
import type { ColumnDef } from '@/composables/useDataTable'
import type { NotificationRule } from '@/types'

const rules = ref<NotificationRule[]>([])
const loading = ref(true)
const form = ref({
  room_token: '',
  room_name: '',
  event_type: '',
  repeat_interval_days: 7,
  overdue_interval_days: 3,
  send_time_moscow: '09:00',
})
const testMessage = ref('Bookuchet test notification')
const result = ref('')

const columns: ColumnDef<NotificationRule>[] = [
  {
    key: 'room',
    label: 'Комната',
    getValue: (row) => row.room_name ?? row.room_token,
  },
  {
    key: 'event_type',
    label: 'Тип',
    getValue: (row) => row.event_type ?? 'all',
  },
  { key: 'repeat_interval_days', label: 'Повтор' },
  { key: 'send_time_moscow', label: 'Время' },
]

onMounted(async () => {
  rules.value = (await api.notificationRules()) as NotificationRule[]
  loading.value = false
})

async function createRule() {
  await api.createNotificationRule(form.value)
  rules.value = (await api.notificationRules()) as NotificationRule[]
}

async function testSend() {
  const response = await api.testNotification({
    room_token: form.value.room_token,
    message: testMessage.value,
  })
  result.value = JSON.stringify(response)
}
</script>

<template>
  <section class="card page">
    <header><h2>Настройки Nextcloud Talk</h2></header>
    <form class="form" @submit.prevent="createRule">
      <label>Room token<input v-model="form.room_token" required /></label>
      <label>Название комнаты<input v-model="form.room_name" /></label>
      <label>Тип события<input v-model="form.event_type" placeholder="contract / grade / ..." /></label>
      <label>Повтор, дней<input v-model.number="form.repeat_interval_days" type="number" /></label>
      <label>Просрочка, дней<input v-model.number="form.overdue_interval_days" type="number" /></label>
      <label>Время (МСК)<input v-model="form.send_time_moscow" /></label>
      <button class="btn" type="submit">Сохранить правило</button>
    </form>

    <div class="test-block">
      <label>Тестовое сообщение<input v-model="testMessage" /></label>
      <button class="btn secondary" @click="testSend">Отправить тест</button>
      <pre v-if="result">{{ result }}</pre>
    </div>

    <DataTable
      :columns="columns"
      :rows="rules"
      row-key="id"
      :loading="loading"
      search-placeholder="Поиск по правилам..."
    />
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
