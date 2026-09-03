<script setup lang="ts">
import { ref } from 'vue'
import EventDetailModal from '@/components/EventDetailModal.vue'
import type { EventItem } from '@/types'
import { formatShortDate, humanizeDatesInText } from '@/utils/dates'
import { labelEventType } from '@/utils/labels'

withDefaults(
  defineProps<{
    events: EventItem[]
    loading?: boolean
    embedded?: boolean
  }>(),
  { embedded: false },
)

const emit = defineEmits<{
  changed: []
}>()

const openEventId = ref<number | null>(null)

function openEvent(id: number) {
  openEventId.value = id
}

function closeEvent() {
  openEventId.value = null
}

function onEventChanged() {
  emit('changed')
}
</script>

<template>
  <section class="upcoming" :class="{ card: !embedded, embedded }">
    <header v-if="!embedded">
      <h3>Ближайшие события</h3>
    </header>
    <div v-if="loading" class="empty">Загрузка...</div>
    <div v-else-if="!events.length" class="empty">Нет ближайших событий</div>
    <TransitionGroup v-else name="slide-up" tag="ul" class="list">
      <li v-for="event in events" :key="event.id">
        <button type="button" class="item" @click="openEvent(event.id)">
          <div>
            <strong>{{ humanizeDatesInText(event.title) }}</strong>
            <p>{{ event.employee_name ?? 'Без сотрудника' }}</p>
          </div>
          <div class="meta">
            <span class="badge">{{ labelEventType(event.event_type) }}</span>
            <time>{{ formatShortDate(event.event_date) }}</time>
          </div>
        </button>
      </li>
    </TransitionGroup>

    <EventDetailModal
      :open="openEventId != null"
      :event-id="openEventId"
      @close="closeEvent"
      @changed="onEventChanged"
    />
  </section>
</template>

<style scoped>
.upcoming {
  padding: 1rem 1.2rem;
}

.upcoming.embedded {
  padding: 0;
}

header h3 {
  margin: 0 0 0.8rem;
}

.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.75rem;
}

.item {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  width: 100%;
  padding: 0.75rem 0;
  border: none;
  border-bottom: 1px solid var(--border);
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  text-decoration: none;
  cursor: pointer;
  transition: background var(--transition);
}

.item:hover {
  background: var(--accent-soft);
}

.item:last-child {
  border-bottom: none;
}

.item p,
.empty {
  margin: 0.2rem 0 0;
  color: var(--muted);
  font-size: 0.92rem;
}

.meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.35rem;
  white-space: nowrap;
}
</style>
