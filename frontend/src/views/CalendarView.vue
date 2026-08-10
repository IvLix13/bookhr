<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AttentionPanel from '@/components/AttentionPanel.vue'
import DayEventsModal from '@/components/DayEventsModal.vue'
import MonthCalendar from '@/components/MonthCalendar.vue'
import PageState from '@/components/PageState.vue'
import UpcomingPanel from '@/components/UpcomingPanel.vue'
import { api } from '@/api/client'
import { useAsyncResource } from '@/composables/useAsyncResource'
import type { EventItem, Paginated } from '@/types'
import { formatLocalDate, monthRange } from '@/utils/dates'

const month = ref(new Date())
const events = ref<EventItem[]>([])
const upcoming = ref<EventItem[]>([])
const selectedDate = ref<string | null>(null)
const dayModalOpen = ref(false)

const calendarResource = useAsyncResource<{ events: EventItem[]; upcoming: EventItem[] }>()

async function loadEvents() {
  const { from, to } = monthRange(month.value)
  await calendarResource.execute(async () => {
    const [monthData, upcomingData] = await Promise.all([
      api.events({ from, to, per_page: 200 }) as Promise<Paginated<EventItem>>,
      api.upcomingEvents(8) as Promise<EventItem[]>,
    ])
    return { events: monthData.items, upcoming: upcomingData }
  })
  if (calendarResource.data.value) {
    events.value = calendarResource.data.value.events
    upcoming.value = calendarResource.data.value.upcoming
  }
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
    <AttentionPanel />
    <PageState
      :loading="calendarResource.isLoading()"
      :refreshing="calendarResource.isRefreshing()"
      :error="calendarResource.error.value"
      @retry="loadEvents()"
    >
      <MonthCalendar
        :events="events"
        :month="month"
        :selected-date="selectedDate"
        @change-month="(value: Date) => { month = value; loadEvents() }"
        @select-day="openDay"
      />
      <UpcomingPanel :events="upcoming" :loading="calendarResource.isBusy()" />
    </PageState>
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
