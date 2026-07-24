<script setup lang="ts">
import { computed } from 'vue'
import type { EventItem } from '@/types'

const props = defineProps<{
  events: EventItem[]
  month: Date
}>()

const emit = defineEmits<{
  changeMonth: [value: Date]
}>()

const weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

const monthLabel = computed(() =>
  props.month.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' }),
)

const days = computed(() => {
  const year = props.month.getFullYear()
  const month = props.month.getMonth()
  const first = new Date(year, month, 1)
  const startOffset = (first.getDay() + 6) % 7
  const total = new Date(year, month + 1, 0).getDate()
  const cells: Array<{ date: Date | null; events: EventItem[] }> = []

  for (let i = 0; i < startOffset; i += 1) {
    cells.push({ date: null, events: [] })
  }

  for (let day = 1; day <= total; day += 1) {
    const date = new Date(year, month, day)
    const iso = date.toISOString().slice(0, 10)
    cells.push({
      date,
      events: props.events.filter((event) => event.event_date === iso),
    })
  }
  return cells
})

function prevMonth() {
  emit('changeMonth', new Date(props.month.getFullYear(), props.month.getMonth() - 1, 1))
}

function nextMonth() {
  emit('changeMonth', new Date(props.month.getFullYear(), props.month.getMonth() + 1, 1))
}
</script>

<template>
  <section class="calendar card">
    <header>
      <button class="btn ghost" @click="prevMonth">←</button>
      <h2>{{ monthLabel }}</h2>
      <button class="btn ghost" @click="nextMonth">→</button>
    </header>

    <div class="weekdays">
      <span v-for="day in weekdays" :key="day">{{ day }}</span>
    </div>

    <div class="grid">
      <article
        v-for="(cell, index) in days"
        :key="index"
        class="day"
        :class="{ muted: !cell.date }"
      >
        <div v-if="cell.date" class="day-number">{{ cell.date.getDate() }}</div>
        <TransitionGroup name="fade" tag="div" class="events">
          <div v-for="event in cell.events.slice(0, 3)" :key="event.id" class="event-chip">
            {{ event.title }}
          </div>
        </TransitionGroup>
      </article>
    </div>
  </section>
</template>

<style scoped>
.calendar {
  padding: 1rem;
}

header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

header h2 {
  margin: 0;
  text-transform: capitalize;
}

.weekdays,
.grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.5rem;
}

.weekdays span {
  text-align: center;
  color: var(--muted);
  font-size: 0.85rem;
}

.day {
  min-height: 110px;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 0.45rem;
  background: #fcfdff;
  transition: transform var(--transition), box-shadow var(--transition);
}

.day:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow);
}

.day.muted {
  opacity: 0.35;
  background: transparent;
  box-shadow: none;
}

.day-number {
  font-size: 0.85rem;
  color: var(--muted);
  margin-bottom: 0.35rem;
}

.events {
  display: grid;
  gap: 0.25rem;
}

.event-chip {
  font-size: 0.72rem;
  padding: 0.25rem 0.35rem;
  border-radius: 8px;
  background: var(--accent-soft);
  color: var(--accent);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
