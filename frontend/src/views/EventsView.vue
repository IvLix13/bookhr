<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { EventItem, Paginated } from '@/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const events = ref<EventItem[]>([])

onMounted(async () => {
  const data = (await api.events('?per_page=200')) as Paginated<EventItem>
  events.value = data.items
})

async function complete(id: number) {
  if (!auth.canEdit()) return
  await api.completeEvent(id)
  events.value = events.value.map((event: EventItem) =>
    event.id === id ? { ...event, status: 'completed' } : event,
  )
}
</script>

<template>
  <section class="card page">
    <header><h2>Мероприятия</h2></header>
    <table class="table">
      <thead>
        <tr>
          <th>Название</th>
          <th>Дата</th>
          <th>Сотрудник</th>
          <th>Тип</th>
          <th>Источник</th>
          <th>Создал</th>
          <th>Статус</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="event in events" :key="event.id">
          <td>{{ event.title }}</td>
          <td>{{ event.event_date }}</td>
          <td>{{ event.employee_name ?? '—' }}</td>
          <td>{{ event.event_type }}</td>
          <td>{{ event.source }}</td>
          <td>{{ event.created_by ?? '—' }}</td>
          <td>{{ event.status }}</td>
          <td>
            <button
              v-if="auth.canEdit() && event.status !== 'completed'"
              class="btn secondary"
              @click="complete(event.id)"
            >
              Выполнить
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<style scoped>
.page { padding: 1rem; }
</style>
