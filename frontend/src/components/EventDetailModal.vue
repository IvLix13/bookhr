<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import EventForm from '@/components/EventForm.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import { useFocusTrap } from '@/composables/useFocusTrap'
import { useAuthStore } from '@/stores/auth'
import type { EventItem } from '@/types'
import { formatDisplayDate, formatShortDate, humanizeDatesInText } from '@/utils/dates'
import { labelEventSource, labelEventType } from '@/utils/labels'
import { getEventStatusMeta, resolveEventStatus } from '@/utils/statuses'

const props = defineProps<{
  open: boolean
  eventId: number | null
}>()

const emit = defineEmits<{
  close: []
  changed: []
}>()

const auth = useAuthStore()
const modalRef = ref<HTMLElement | null>(null)
const event = ref<EventItem | null>(null)
const loading = ref(false)
const error = ref('')
const actionBusy = ref(false)
const comment = ref('')
const extensionTermYears = ref('1')
const targetGradeId = ref('')
const newPassportValidUntil = ref('')
const editing = ref(false)

const isContractReport = computed(() => {
  if (!event.value) return false
  return (
    event.value.event_type === 'report' &&
    (event.value.reference_type === 'contract' ||
      event.value.title.toLowerCase().includes('договор'))
  )
})

const isGradePromotion = computed(
  () =>
    event.value?.event_type === 'grade' &&
    event.value?.grade_event_kind !== 'preparation',
)
const gradeCompletion = computed(() =>
  isGradePromotion.value ? (event.value?.grade_completion ?? null) : null,
)
const requiresGradeChoice = computed(
  () => gradeCompletion.value?.requires_selection === true,
)

const isPassportPreparation = computed(
  () => event.value?.passport_completion?.requires_new_date === true,
)
const passportCompletion = computed(() => event.value?.passport_completion ?? null)
const requiresPassportDate = computed(() => isPassportPreparation.value)

const { activate, deactivate } = useFocusTrap(modalRef, () => props.open)

const statusKey = computed(() =>
  event.value
    ? resolveEventStatus(event.value.status, event.value.effective_status)
    : '',
)

const statusMeta = computed(() => getEventStatusMeta(statusKey.value))

const isOpenStatus = computed(() => {
  const status = event.value?.status
  return status === 'planned' || status === 'overdue'
})

const isClosedStatus = computed(() => {
  const status = event.value?.status
  return status === 'completed' || status === 'cancelled'
})

const canAct = computed(() => auth.canEdit() && !!event.value)

const isManualEvent = computed(() => event.value?.source === 'manual')

const canEditEvent = computed(
  () =>
    canAct.value &&
    isManualEvent.value &&
    isOpenStatus.value,
)

const canEditReportDate = computed(() => {
  if (!canAct.value || !isContractReport.value || !event.value) return false
  return event.value.status !== 'cancelled'
})

const displayedReportDate = computed(() => {
  if (!event.value) return ''
  if (event.value.status === 'completed' && event.value.completed_at) {
    return event.value.completed_at.slice(0, 10)
  }
  return event.value.event_date
})

const reportDateDraft = ref('')

async function loadEvent() {
  if (props.eventId == null) {
    event.value = null
    return
  }
  loading.value = true
  error.value = ''
  try {
    event.value = (await api.getEvent(props.eventId)) as EventItem
    reportDateDraft.value =
      event.value.status === 'completed' && event.value.completed_at
        ? event.value.completed_at.slice(0, 10)
        : event.value.event_date
    const candidates = event.value.grade_completion?.candidates ?? []
    targetGradeId.value = candidates.length === 1 ? String(candidates[0].id) : ''
    newPassportValidUntil.value =
      event.value.passport_completion?.suggested_new_valid_until ?? ''
  } catch (err) {
    error.value = normalizeError(err)
    event.value = null
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.open, props.eventId] as const,
  ([open]) => {
    if (open) {
      comment.value = ''
      extensionTermYears.value = '1'
      targetGradeId.value = ''
      newPassportValidUntil.value = ''
      editing.value = false
      void loadEvent()
    } else {
      event.value = null
      error.value = ''
      comment.value = ''
      extensionTermYears.value = '1'
      targetGradeId.value = ''
      newPassportValidUntil.value = ''
      reportDateDraft.value = ''
      editing.value = false
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

function onKeydown(keyboardEvent: KeyboardEvent) {
  if (keyboardEvent.key === 'Escape' && props.open) {
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

async function runAction(action: 'complete' | 'cancel' | 'reopen') {
  if (!event.value || !canAct.value) return
  if (action === 'cancel') {
    const confirmed = window.confirm('Отменить мероприятие? Это действие нельзя отменить.')
    if (!confirmed) return
  }
  actionBusy.value = true
  error.value = ''
  try {
    const id = event.value.id
    const note = comment.value.trim() || undefined
    switch (action) {
      case 'complete': {
        if (requiresGradeChoice.value && !targetGradeId.value) {
          throw new Error('Выберите следующий грейд')
        }
        if (requiresPassportDate.value && !newPassportValidUntil.value) {
          throw new Error('Укажите новый срок действия паспорта')
        }
        const termYears =
          isContractReport.value && extensionTermYears.value
            ? Number(extensionTermYears.value)
            : undefined
        const options = {
          ...(termYears !== undefined ? { extension_term_years: termYears } : {}),
          ...(targetGradeId.value
            ? { target_grade_id: Number(targetGradeId.value) }
            : {}),
          ...(newPassportValidUntil.value
            ? { new_passport_valid_until: newPassportValidUntil.value }
            : {}),
        }
        event.value = (
          Object.keys(options).length
            ? await api.completeEvent(id, note, options)
            : await api.completeEvent(id, note)
        ) as EventItem
        break
      }
      case 'cancel':
        event.value = (await api.cancelEvent(id, note)) as EventItem
        break
      case 'reopen':
        event.value = (await api.reopenEvent(id)) as EventItem
        break
      default: {
        const _exhaustive: never = action
        return _exhaustive
      }
    }
    comment.value = ''
    emit('changed')
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    actionBusy.value = false
  }
}

async function deleteEvent() {
  if (!event.value || !canAct.value || !isManualEvent.value) return
  const confirmed = window.confirm('Удалить мероприятие? Это действие нельзя отменить.')
  if (!confirmed) return
  actionBusy.value = true
  error.value = ''
  try {
    await api.deleteEvent(event.value.id)
    emit('changed')
    closeModal()
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    actionBusy.value = false
  }
}

async function onUpdated() {
  editing.value = false
  await loadEvent()
  emit('changed')
}

async function saveReportDate() {
  if (!event.value || !canEditReportDate.value) return
  actionBusy.value = true
  error.value = ''
  try {
    await api.updateEvent(event.value.id, { event_date: reportDateDraft.value })
    await loadEvent()
    emit('changed')
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    actionBusy.value = false
  }
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
          :aria-label="humanizeDatesInText(event?.title) || 'Мероприятие'"
        >
          <header class="modal-header">
            <div>
              <h2>{{ humanizeDatesInText(event?.title) || 'Мероприятие' }}</h2>
              <p v-if="event">{{ formatDisplayDate(event.event_date) }}</p>
            </div>
            <button class="btn ghost" type="button" aria-label="Закрыть" @click="closeModal">
              ×
            </button>
          </header>

          <div v-if="loading" class="state">
            <span class="spinner"></span> Загрузка...
          </div>
          <div v-else-if="error && !event" class="state error">{{ error }}</div>

          <div v-else-if="event" class="body">
            <EventForm
              v-if="editing"
              compact
              :initial-date="event.event_date"
              :event="event"
              @updated="onUpdated"
              @cancel="editing = false"
            />

            <template v-else>
            <dl class="details">
              <div>
                <dt>Статус</dt>
                <dd>
                  <StatusBadge :label="statusMeta.label" :variant="statusMeta.variant" />
                </dd>
              </div>
              <div>
                <dt>Тип</dt>
                <dd>{{ labelEventType(event.event_type) }}</dd>
              </div>
              <div>
                <dt>Сотрудник</dt>
                <dd>{{ event.employee_name ?? 'Без сотрудника' }}</dd>
              </div>
              <div>
                <dt>Источник</dt>
                <dd>{{ labelEventSource(event.source) }}</dd>
              </div>
              <div>
                <dt>Создал</dt>
                <dd>{{ event.created_by ?? '—' }}</dd>
              </div>
              <div>
                <dt>Создано</dt>
                <dd>{{ formatShortDate(event.created_at) }}</dd>
              </div>
              <div v-if="event.completed_at">
                <dt>Выполнено</dt>
                <dd>{{ formatShortDate(event.completed_at) }}</dd>
              </div>
              <div v-if="event.completion_comment" class="full">
                <dt>Комментарий</dt>
                <dd>{{ humanizeDatesInText(event.completion_comment) }}</dd>
              </div>
              <div v-if="event.description" class="full">
                <dt>Описание</dt>
                <dd>{{ humanizeDatesInText(event.description) }}</dd>
              </div>
            </dl>

            <p v-if="error" class="state error inline">{{ error }}</p>

            <footer v-if="canAct" class="actions">
              <div v-if="canEditEvent" class="action-buttons">
                <button
                  class="btn secondary"
                  type="button"
                  :disabled="actionBusy"
                  @click="editing = true"
                >
                  Редактировать
                </button>
                <button
                  class="btn ghost danger"
                  type="button"
                  :disabled="actionBusy"
                  @click="deleteEvent"
                >
                  Удалить
                </button>
              </div>
              <div v-if="canEditReportDate" class="extension-row">
                <label for="report-date-input">Дата рапорта:</label>
                <input
                  id="report-date-input"
                  v-model="reportDateDraft"
                  type="date"
                  :disabled="actionBusy"
                  required
                />
                <button
                  class="btn secondary"
                  type="button"
                  :disabled="actionBusy || !reportDateDraft || reportDateDraft === displayedReportDate"
                  @click="saveReportDate"
                >
                  Сохранить дату
                </button>
              </div>
              <template v-if="isOpenStatus">
                <div v-if="isContractReport" class="extension-row">
                  <label for="extension-term-select">Срок продления договора:</label>
                  <select
                    id="extension-term-select"
                    v-model="extensionTermYears"
                    :disabled="actionBusy"
                  >
                    <option value="1">1 год</option>
                    <option value="2">2 года</option>
                    <option value="3">3 года</option>
                    <option value="5">5 лет</option>
                  </select>
                </div>
                <div v-if="gradeCompletion?.candidates.length" class="extension-row">
                  <label for="target-grade-select">Следующий грейд:</label>
                  <select
                    id="target-grade-select"
                    v-model="targetGradeId"
                    :disabled="actionBusy || gradeCompletion.candidates.length === 1"
                    :required="requiresGradeChoice"
                  >
                    <option v-if="requiresGradeChoice" value="" disabled>Выберите грейд</option>
                    <option
                      v-for="candidate in gradeCompletion.candidates"
                      :key="candidate.id"
                      :value="String(candidate.id)"
                    >
                      {{ candidate.name }} (ранг {{ candidate.rank }})
                    </option>
                  </select>
                </div>
                <p v-if="gradeCompletion?.blocked_reason" class="state error inline">
                  {{ gradeCompletion.blocked_reason }}
                </p>
                <div v-if="isPassportPreparation" class="extension-row passport-row">
                  <label for="new-passport-date">Новый срок паспорта:</label>
                  <input
                    id="new-passport-date"
                    v-model="newPassportValidUntil"
                    type="date"
                    :disabled="actionBusy"
                    :required="requiresPassportDate"
                    readonly
                  />
                </div>
                <p v-if="passportCompletion?.current_valid_until" class="hint inline">
                  Текущий срок:
                  {{ formatShortDate(passportCompletion.current_valid_until) }}
                  (новый — +5 лет)
                </p>
                <input
                  v-model="comment"
                  type="text"
                  placeholder="Комментарий (необязательно)"
                  aria-label="Комментарий к действию"
                  :disabled="actionBusy"
                />
                <div class="action-buttons">
                  <button
                    class="btn"
                    type="button"
                    :disabled="
                      actionBusy ||
                      Boolean(gradeCompletion?.blocked_reason) ||
                      (requiresGradeChoice && !targetGradeId) ||
                      (requiresPassportDate && !newPassportValidUntil)
                    "
                    @click="runAction('complete')"
                  >
                    {{ actionBusy ? '...' : 'Выполнить' }}
                  </button>
                  <button
                    class="btn secondary"
                    type="button"
                    :disabled="actionBusy"
                    @click="runAction('cancel')"
                  >
                    Отменить
                  </button>
                </div>
              </template>
              <template v-else-if="isClosedStatus">
                <button
                  class="btn secondary"
                  type="button"
                  :disabled="actionBusy"
                  @click="runAction('reopen')"
                >
                  {{ actionBusy ? '...' : 'Переоткрыть' }}
                </button>
              </template>
            </footer>
            </template>
          </div>
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
  width: min(640px, 100%);
  max-height: calc(100vh - 2rem);
  overflow: auto;
  padding: 1rem;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: start;
}

.modal-header h2 {
  margin: 0;
  font-size: 1.25rem;
  text-transform: none;
}

.modal-header p {
  margin: 0.35rem 0 0;
  color: var(--muted);
}

.body {
  margin-top: 1rem;
  display: grid;
  gap: 1rem;
}

.details {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.85rem 1rem;
  margin: 0;
}

.details dt {
  margin: 0;
  color: var(--muted);
  font-size: 0.85rem;
}

.details dd {
  margin: 0.2rem 0 0;
}

.details .full {
  grid-column: 1 / -1;
}

.actions {
  display: grid;
  gap: 0.75rem;
  padding-top: 0.25rem;
  border-top: 1px solid var(--border);
}

.extension-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
  font-size: 0.9rem;
}

.extension-row select,
.extension-row input[type='date'] {
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
}

.hint.inline {
  margin: 0;
  color: var(--muted);
  font-size: 0.88rem;
}

.actions input {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.55rem 0.75rem;
  width: 100%;
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.btn.danger {
  color: var(--danger);
}

.state {
  margin-top: 1rem;
  color: var(--muted);
}

.state.inline {
  margin: 0;
}

.state.error {
  color: var(--danger);
}

.state .spinner {
  margin-right: 0.4rem;
}

@media (max-width: 560px) {
  .details {
    grid-template-columns: 1fr;
  }
}
</style>
