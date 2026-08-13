<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CalendarFeedPanel from '@/components/CalendarFeedPanel.vue'
import DayEventsModal from '@/components/DayEventsModal.vue'
import EventDetailModal from '@/components/EventDetailModal.vue'
import MonthCalendar from '@/components/MonthCalendar.vue'
import PageState from '@/components/PageState.vue'
import { api } from '@/api/client'
import { useAsyncResource } from '@/composables/useAsyncResource'
import type { EventItem, Paginated } from '@/types'
import { formatLocalDate, monthRange } from '@/utils/dates'

const route = useRoute()
const router = useRouter()

const month = ref(new Date())
const events = ref<EventItem[]>([])
const upcoming = ref<EventItem[]>([])
const selectedDate = ref<string | null>(null)
const dayModalOpen = ref(false)

const calendarResource = useAsyncResource<{ events: EventItem[]; upcoming: EventItem[] }>()

const openEventId = computed(() => {
  const raw = route.query.event
  const value = Array.isArray(raw) ? raw[0] : raw
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
})

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

function closeEventModal() {
  const nextQuery = { ...route.query }
  delete nextQuery.event
  void router.replace({ query: nextQuery })
}

async function onDayChanged() {
  await loadEvents()
}

async function onEventChanged() {
  await loadEvents()
}

onMounted(loadEvents)
</script>

<template>
  <div class="calendar-page">
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
    </PageState>
    <CalendarFeedPanel :events="upcoming" :loading="calendarResource.isBusy()" />
    <DayEventsModal
      :open="dayModalOpen"
      :date="selectedDate ?? formatLocalDate(new Date())"
      @close="closeDayModal"
      @changed="onDayChanged"
    />
    <EventDetailModal
      :open="openEventId != null"
      :event-id="openEventId"
      @close="closeEventModal"
      @changed="onEventChanged"
    />
  </div>
</template>

<style scoped>
.calendar-page {
  display: grid;
  gap: 1rem;
}
</style>
