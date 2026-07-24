<script setup lang="ts">
import type { EventItem } from '@/types'

defineProps<{
  events: EventItem[]
  loading?: boolean
}>()
</script>

<template>
  <section class="upcoming card">
    <header>
      <h3>Ближайшие события</h3>
    </header>
    <div v-if="loading" class="empty">Загрузка...</div>
    <div v-else-if="!events.length" class="empty">Нет ближайших событий</div>
    <TransitionGroup v-else name="slide-up" tag="ul" class="list">
      <li v-for="event in events" :key="event.id" class="item">
        <div>
          <strong>{{ event.title }}</strong>
          <p>{{ event.employee_name ?? 'Без сотрудника' }}</p>
        </div>
        <div class="meta">
          <span class="badge">{{ event.event_type }}</span>
          <time>{{ event.event_date }}</time>
        </div>
      </li>
    </TransitionGroup>
  </section>
</template>

<style scoped>
.upcoming {
  padding: 1rem 1.2rem;
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
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--border);
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
