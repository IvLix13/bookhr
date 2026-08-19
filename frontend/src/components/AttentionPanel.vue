<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import EventDetailModal from '@/components/EventDetailModal.vue'
import PageState from '@/components/PageState.vue'
import { api } from '@/api/client'
import { useAsyncResource } from '@/composables/useAsyncResource'
import {
  attentionEventId,
  attentionItemKey,
  canOpenAttentionEvent,
  resolveAttentionRoute,
  type BackendAttentionItem,
} from '@/utils/attention'

withDefaults(
  defineProps<{
    embedded?: boolean
  }>(),
  { embedded: false },
)

const emit = defineEmits<{
  changed: []
}>()

const openEventId = ref<number | null>(null)
const selectedCategory = ref<string | null>(null)

interface AttentionPayload {
  total: number
  counts: Record<string, number>
  items: BackendAttentionItem[]
}

const resource = useAsyncResource<AttentionPayload>()

const summary = computed(() => resource.data.value)
const counts = computed(() => summary.value?.counts ?? {})
const items = computed(() => summary.value?.items ?? [])
const filteredItems = computed(() => {
  if (!selectedCategory.value) return items.value
  return items.value.filter((item) => item.category === selectedCategory.value)
})

const visibleTotal = computed(() =>
  selectedCategory.value ? filteredItems.value.length : (summary.value?.total ?? 0),
)

const categoryLabels: Record<string, string> = {
  events: 'Мероприятия',
  contracts: 'Договоры',
  passports: 'Паспорта',
  grades: 'Грейды',
  tenure: 'Награды за стаж',
}

function categoryLabel(key: string): string {
  return categoryLabels[key] ?? key
}

function severityClass(severity: BackendAttentionItem['severity']): string {
  switch (severity) {
    case 'danger':
      return 'danger'
    case 'warning':
      return 'warning'
    case 'info':
      return 'info'
    default: {
      const _exhaustive: never = severity
      return _exhaustive
    }
  }
}

async function loadAttention() {
  await resource.execute(() => api.attention({ limit: 12 }) as Promise<AttentionPayload>)
  selectedCategory.value = null
}

function toggleCategoryFilter(category: string) {
  selectedCategory.value = selectedCategory.value === category ? null : category
}

function isCategoryActive(category: string): boolean {
  return selectedCategory.value === category
}

function openItemEvent(item: BackendAttentionItem) {
  const eventId = attentionEventId(item)
  if (eventId == null) return
  openEventId.value = eventId
}

function closeEventModal() {
  openEventId.value = null
}

async function onEventChanged() {
  await loadAttention()
  emit('changed')
}

onMounted(() => {
  void loadAttention()
})

defineExpose({ reload: loadAttention })
</script>

<template>
  <section class="attention" :class="{ card: !embedded, embedded }">
    <header class="attention-header">
      <div>
        <h3 v-if="!embedded">Требует внимания</h3>
        <p v-if="summary">
          {{
            selectedCategory
              ? `Показано: ${visibleTotal} · ${categoryLabel(selectedCategory)}`
              : `Всего: ${visibleTotal}`
          }}
        </p>
      </div>
      <button
        type="button"
        class="btn ghost"
        :disabled="resource.isBusy()"
        @click="loadAttention()"
      >
        Обновить
      </button>
    </header>

    <PageState
      :loading="resource.isLoading()"
      :refreshing="resource.isRefreshing()"
      :error="resource.error.value"
      :empty="!resource.isBusy() && !filteredItems.length"
      :empty-text="
        selectedCategory
          ? `Нет задач в категории «${categoryLabel(selectedCategory)}»`
          : 'Нет срочных задач'
      "
      @retry="loadAttention()"
    >
      <TransitionGroup
        v-if="Object.keys(counts).length"
        tag="div"
        name="list"
        class="attention-counts"
      >
        <button
          v-for="(count, key) in counts"
          :key="key"
          type="button"
          class="count-chip"
          :class="{ active: isCategoryActive(String(key)) }"
          :aria-pressed="isCategoryActive(String(key))"
          @click="toggleCategoryFilter(String(key))"
        >
          <span class="count-label">{{ categoryLabel(String(key)) }}</span>
          <strong>{{ count }}</strong>
        </button>
      </TransitionGroup>

      <TransitionGroup tag="ul" name="list" class="attention-list">
        <li v-for="item in filteredItems" :key="attentionItemKey(item)" class="attention-item">
          <button
            v-if="canOpenAttentionEvent(item)"
            type="button"
            class="attention-link"
            :class="severityClass(item.severity)"
            @click="openItemEvent(item)"
          >
            <div class="attention-main">
              <strong>{{ item.title }}</strong>
              <p v-if="item.subtitle">{{ item.subtitle }}</p>
            </div>
            <div class="attention-meta">
              <span class="badge" :class="severityClass(item.severity)">
                {{ categoryLabel(item.category) }}
              </span>
              <time v-if="item.due_date">{{ item.due_date }}</time>
            </div>
          </button>
          <RouterLink
            v-else
            :to="resolveAttentionRoute(item)"
            class="attention-link"
            :class="severityClass(item.severity)"
          >
            <div class="attention-main">
              <strong>{{ item.title }}</strong>
              <p v-if="item.subtitle">{{ item.subtitle }}</p>
            </div>
            <div class="attention-meta">
              <span class="badge" :class="severityClass(item.severity)">
                {{ categoryLabel(item.category) }}
              </span>
              <time v-if="item.due_date">{{ item.due_date }}</time>
            </div>
          </RouterLink>
        </li>
      </TransitionGroup>
    </PageState>

    <EventDetailModal
      :open="openEventId != null"
      :event-id="openEventId"
      @close="closeEventModal"
      @changed="onEventChanged"
    />
  </section>
</template>

<style scoped>
.attention {
  padding: 1rem 1.2rem;
}

.attention.embedded {
  padding: 0;
}

.attention-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.attention.embedded .attention-header {
  align-items: center;
}

.attention-header h3 {
  margin: 0;
}

.attention-header p {
  margin: 0.25rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
}

.attention-counts {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.85rem;
  position: relative;
}

.count-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  padding: 0.25rem 0.65rem;
  font-size: 0.85rem;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
  transition: background var(--transition), transform var(--transition),
    border-color var(--transition);
}

.count-chip:hover {
  background: var(--accent-soft);
  border-color: var(--accent-border, var(--accent));
  transform: translateY(-1px);
}

.count-chip.active {
  background: var(--accent-soft);
  border-color: var(--accent-border, var(--accent));
  box-shadow: inset 0 0 0 1px var(--accent-border, var(--accent));
}

.count-label {
  color: var(--muted);
}

.attention-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.5rem;
  position: relative;
}

.attention-link {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  transition: background var(--transition), transform var(--transition),
    box-shadow var(--transition);
}

button.attention-link {
  width: 100%;
  margin: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.attention-link:hover {
  background: var(--bg);
  transform: translateX(3px);
  box-shadow: var(--shadow);
}

.attention-main p {
  margin: 0.2rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
}

.attention-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.35rem;
  white-space: nowrap;
}

.attention-meta time {
  font-size: 0.85rem;
  color: var(--muted);
}

.attention-link.warning {
  border-color: #f3dfad;
}

.attention-link.danger {
  border-color: #efb8b8;
}

.badge.info {
  background: var(--accent-soft);
  color: var(--accent);
}
</style>
