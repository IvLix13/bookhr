<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import EventForm from '@/components/EventForm.vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import { useFocusTrap } from '@/composables/useFocusTrap'
import type { EventItem, Paginated } from '@/types'
import StatusBadge from '@/components/StatusBadge.vue'
import { formatDisplayDate } from '@/utils/dates'
import { labelEventType } from '@/utils/labels'
import { getEventStatusMeta, resolveEventStatus } from '@/utils/statuses'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  open: boolean
  date: string
}>()

const emit = defineEmits<{
  close: []
  changed: []
}>()

const auth = useAuthStore()
const modalRef = ref<HTMLElement | null>(null)
const events = ref<EventItem[]>([])
const loading = ref(false)
const error = ref('')
const showForm = ref(false)
const completingId = ref<number | null>(null)
const comments = ref<Record<number, string>>({})

const { activate, deactivate } = useFocusTrap(modalRef, () => props.open)

const title = computed(() => formatDisplayDate(props.date))

async function loadDayEvents() {
  loading.value = true
  error.value = ''
  try {
    const data = (await api.events({
      from: props.date,
      to: props.date,
      per_page: 200,
    })) as Paginated<EventItem>
    events.value = data.items
  } catch (err) {
    error.value = normalizeError(err)
    events.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.open, props.date] as const,
  ([open]) => {
    if (open) {
      showForm.value = false
      loadDayEvents()
    }
  },
  { immediate: true },
)

watch(
  () => props.open,
  (open) => {
    if (open) activate()
    else deactivate()
  },
)

function closeModal() {
  emit('close')
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.open) {
    closeModal()
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      window.addEventListener('keydown', onKeydown)
    } else {
      window.removeEventListener('keydown', onKeydown)
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  deactivate()
})

async function completeEvent(id: number) {
  if (!auth.canEdit()) return
  completingId.value = id
  error.value = ''
  try {
    await api.completeEvent(id, comments.value[id] || undefined)
    emit('changed')
    await loadDayEvents()
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    completingId.value = null
  }
}

async function onCreated() {
  showForm.value = false
  emit('changed')
  await loadDayEvents()
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="overlay" @click.self="closeModal">
        <section
        ref="modalRef"
        class="modal card"
        role="dialog"
        aria-modal="true"
        :aria-label="`Мероприятия на ${date}`"
      >
        <header class="modal-header">
          <div>
            <h2>{{ title }}</h2>
            <p>{{ events.length }} мероприятий</p>
          </div>
          <button class="btn ghost" type="button" aria-label="Закрыть" @click="closeModal">×</button>
        </header>

        <div v-if="loading" class="state"><span class="spinner"></span> Загрузка...</div>
        <div v-else-if="error" class="state error">{{ error }}</div>

        <TransitionGroup v-else-if="events.length" tag="ul" name="list" class="list">
          <li v-for="event in events" :key="event.id" class="item">
            <div class="item-main">
              <strong>{{ event.title }}</strong>
              <p>{{ event.employee_name ?? 'Без сотрудника' }}</p>
              <p v-if="event.description" class="description">{{ event.description }}</p>
            </div>
            <div class="item-meta">
              <span class="badge">{{ labelEventType(event.event_type) }}</span>
              <StatusBadge
                :label="getEventStatusMeta(resolveEventStatus(event.status, event.effective_status)).label"
                :variant="getEventStatusMeta(resolveEventStatus(event.status, event.effective_status)).variant"
              />
              <template v-if="auth.canEdit() && event.status !== 'completed' && event.status !== 'cancelled'">
                <input
                  v-model="comments[event.id]"
                  type="text"
                  placeholder="Комментарий"
                  aria-label="Комментарий к завершению"
                />
                <button
                  class="btn secondary"
                  type="button"
                  :disabled="completingId === event.id"
                  @click="completeEvent(event.id)"
                >
                  {{ completingId === event.id ? '...' : 'Выполнить' }}
                </button>
              </template>
            </div>
          </li>
        </TransitionGroup>
        <div v-else class="state">На этот день мероприятий нет</div>

        <footer class="modal-footer">
          <button
            v-if="auth.canEdit() && !showForm"
            class="btn"
            type="button"
            @click="showForm = true"
          >
            + Добавить мероприятие
          </button>
          <Transition name="slide-up">
            <EventForm
              v-if="showForm && auth.canEdit()"
              compact
              :initial-date="date"
              @created="onCreated"
              @cancel="showForm = false"
            />
          </Transition>
        </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: grid;
  place-items: center;
  padding: 1rem;
  z-index: 1000;
}

.modal {
  width: min(760px, 100%);
  max-height: calc(100vh - 2rem);
  overflow: auto;
  padding: 1rem;
}

.modal-header,
.modal-footer {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: start;
}

.modal-header h2 {
  margin: 0;
  text-transform: capitalize;
}

.modal-header p {
  margin: 0.35rem 0 0;
  color: var(--muted);
}

.modal-footer {
  margin-top: 1rem;
  flex-direction: column;
}

.list {
  list-style: none;
  margin: 1rem 0 0;
  padding: 0;
  display: grid;
  gap: 0.75rem;
  position: relative;
}

.item {
  display: grid;
  gap: 0.75rem;
  padding: 0.85rem 0;
  border-bottom: 1px solid var(--border);
}

.state .spinner {
  margin-right: 0.4rem;
}

.item:last-child {
  border-bottom: none;
}

.item-main p {
  margin: 0.25rem 0 0;
  color: var(--muted);
}

.description {
  font-size: 0.92rem;
}

.item-meta {
  display: grid;
  gap: 0.5rem;
}

.item-meta input {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.55rem 0.75rem;
}

.state {
  margin-top: 1rem;
  color: var(--muted);
}

.state.error {
  color: var(--danger);
}
</style>
