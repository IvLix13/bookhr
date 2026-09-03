<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import EventDetailModal from '@/components/EventDetailModal.vue'
import PageState from '@/components/PageState.vue'
import { api } from '@/api/client'
import { useAsyncResource } from '@/composables/useAsyncResource'
import {
  attentionEventId,
  attentionItemKey,
  type BackendAttentionItem,
} from '@/utils/attention'
import { formatShortDate, humanizeDatesInText } from '@/utils/dates'

withDefaults(
  defineProps<{
    embedded?: boolean
  }>(),
  { embedded: false },
)

const emit = defineEmits<{
  changed: []
}>()

const ATTENTION_LIMIT = 12
const ATTENTION_CATEGORY_LIMIT = 50

const openEventId = ref<number | null>(null)
const selectedCategory = ref<string | null>(null)
const chipCounts = ref<Record<string, number>>({})

interface AttentionPayload {
  total: number
  counts: Record<string, number>
  items: BackendAttentionItem[]
}

const resource = useAsyncResource<AttentionPayload>()

const summary = computed(() => resource.data.value)
const counts = computed(() =>
  Object.keys(chipCounts.value).length ? chipCounts.value : (summary.value?.counts ?? {}),
)
const items = computed(() => summary.value?.items ?? [])

const visibleTotal = computed(() => {
  if (!summary.value) return 0
  if (selectedCategory.value) {
    return chipCounts.value[selectedCategory.value] ?? items.value.length
  }
  return summary.value.total
})

const categoryLabels: Record<string, string> = {
  events: 'Мероприятия',
  contracts: 'Договоры',
  passports: 'Паспорта',
  grades: 'Грейды',
  tenure: 'Награды за стаж',
}

const categoryOrder = ['events', 'contracts', 'passports', 'grades', 'tenure'] as const

const orderedCounts = computed(() => {
  const source = counts.value
  const ordered: Record<string, number> = {}
  for (const key of categoryOrder) {
    if (key in source) ordered[key] = source[key]
  }
  for (const [key, value] of Object.entries(source)) {
    if (!(key in ordered)) ordered[key] = value
  }
  return ordered
})

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

async function loadAttentionAll() {
  selectedCategory.value = null
  await resource.execute(async () => {
    const data = (await api.attention({ limit: ATTENTION_LIMIT })) as AttentionPayload
    chipCounts.value = data.counts
    return data
  })
}

async function loadAttentionCategory(category: string) {
  selectedCategory.value = category
  await resource.execute(async () => {
    const filtered = (await api.attention({
      limit: ATTENTION_CATEGORY_LIMIT,
      categories: category,
    })) as AttentionPayload
    return {
      total: chipCounts.value[category] ?? filtered.total,
      counts: chipCounts.value,
      items: filtered.items,
    }
  })
}

async function loadAttention() {
  if (selectedCategory.value) {
    await loadAttentionCategory(selectedCategory.value)
    return
  }
  await loadAttentionAll()
}

async function toggleCategoryFilter(category: string) {
  if (selectedCategory.value === category) {
    await loadAttentionAll()
    return
  }
  await loadAttentionCategory(category)
}

function isCategoryActive(category: string): boolean {
  return selectedCategory.value === category
}

function openAttentionItem(item: BackendAttentionItem) {
  const eventId = attentionEventId(item)
  if (eventId != null) {
    openEventId.value = eventId
    return
  }
  void loadAttentionCategory(item.category)
}

function closeEventModal() {
  openEventId.value = null
}

async function onEventChanged() {
  await loadAttention()
  emit('changed')
}

onMounted(() => {
  void loadAttentionAll()
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
              ? `Показано: ${items.length} · ${categoryLabel(selectedCategory)}`
              : `Всего: ${visibleTotal}`
          }}
        </p>
      </div>
      <button
        type="button"
        class="btn ghost"
        :disabled="resource.isBusy()"
        @click="loadAttentionAll()"
      >
        Обновить
      </button>
    </header>

    <PageState
      :loading="resource.isLoading()"
      :refreshing="resource.isRefreshing()"
      :error="resource.error.value"
      :empty="!resource.isBusy() && !items.length"
      :empty-text="
        selectedCategory
          ? `Нет задач в категории «${categoryLabel(selectedCategory)}»`
          : 'Нет срочных задач'
      "
      @retry="loadAttention()"
    >
      <TransitionGroup
        v-if="Object.keys(orderedCounts).length"
        tag="div"
        name="list"
        class="attention-counts"
      >
        <button
          v-for="(count, key) in orderedCounts"
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
        <li v-for="item in items" :key="attentionItemKey(item)" class="attention-item">
          <button
            type="button"
            class="attention-link"
            :class="severityClass(item.severity)"
            @click="openAttentionItem(item)"
          >
            <div class="attention-main">
              <strong>{{ humanizeDatesInText(item.title) }}</strong>
              <p v-if="item.subtitle">{{ humanizeDatesInText(item.subtitle) }}</p>
            </div>
            <div class="attention-meta">
              <span class="badge" :class="severityClass(item.severity)">
                {{ categoryLabel(item.category) }}
              </span>
              <time v-if="item.due_date">{{ formatShortDate(item.due_date) }}</time>
            </div>
          </button>
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
  width: 100%;
  margin: 0;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: background var(--transition), transform var(--transition),
    box-shadow var(--transition);
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
