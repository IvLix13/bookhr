<script setup lang="ts">
import { onMounted, ref } from 'vue'
import MonthCalendar from '@/components/MonthCalendar.vue'
import UpcomingPanel from '@/components/UpcomingPanel.vue'
import { api } from '@/api/client'
import type { EventItem } from '@/types'

const month = ref(new Date())
const events = ref<EventItem[]>([])
const upcoming = ref<EventItem[]>([])
const loading = ref(true)

async function loadEvents() {
  loading.value = true
  const year = month.value.getFullYear()
  const monthIndex = month.value.getMonth()
  const from = new Date(year, monthIndex, 1).toISOString().slice(0, 10)
  const to = new Date(year, monthIndex + 1, 0).toISOString().slice(0, 10)
  const [monthData, upcomingData] = await Promise.all([
    api.events(`?from=${from}&to=${to}&per_page=500`) as Promise<{ items: EventItem[] }>,
    api.upcomingEvents(8) as Promise<EventItem[]>,
  ])
  events.value = monthData.items
  upcoming.value = upcomingData
  loading.value = false
}

onMounted(loadEvents)
</script>

<template>
  <div class="calendar-page">
    <MonthCalendar
      :events="events"
      :month="month"
      @change-month="(value: Date) => { month = value; loadEvents() }"
    />
    <UpcomingPanel :events="upcoming" :loading="loading" />
  </div>
</template>

<style scoped>
.calendar-page {
  display: grid;
  gap: 1rem;
}
</style>
