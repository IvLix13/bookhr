<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DayEventsModal from '@/components/DayEventsModal.vue'
import MonthCalendar from '@/components/MonthCalendar.vue'
import UpcomingPanel from '@/components/UpcomingPanel.vue'
import { api } from '@/api/client'
import type { EventItem } from '@/types'
import { formatLocalDate, monthRange } from '@/utils/dates'

const month = ref(new Date())
const events = ref<EventItem[]>([])
const upcoming = ref<EventItem[]>([])
const loading = ref(true)
const selectedDate = ref<string | null>(null)
const dayModalOpen = ref(false)

async function loadEvents() {
  loading.value = true
  const { from, to } = monthRange(month.value)
  const [monthData, upcomingData] = await Promise.all([
    api.events(`?from=${from}&to=${to}&per_page=200`) as Promise<{ items: EventItem[] }>,
    api.upcomingEvents(8) as Promise<EventItem[]>,
  ])
  events.value = monthData.items
  upcoming.value = upcomingData
  loading.value = false
}

function openDay(date: Date) {
  selectedDate.value = formatLocalDate(date)
  dayModalOpen.value = true
}

function closeDayModal() {
  dayModalOpen.value = false
}

async function onDayChanged() {
  await loadEvents()
}

onMounted(loadEvents)
</script>

<template>
  <div class="calendar-page">
    <MonthCalendar
      :events="events"
      :month="month"
      :selected-date="selectedDate"
      @change-month="(value: Date) => { month = value; loadEvents() }"
      @select-day="openDay"
    />
    <UpcomingPanel :events="upcoming" :loading="loading" />
    <DayEventsModal
      :open="dayModalOpen"
      :date="selectedDate ?? formatLocalDate(new Date())"
      @close="closeDayModal"
      @changed="onDayChanged"
    />
  </div>
</template>

<style scoped>
.calendar-page {
  display: grid;
  gap: 1rem;
}
</style>
