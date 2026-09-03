<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import { normalizeError } from '@/api/errors'
import { useFocusTrap } from '@/composables/useFocusTrap'
import { MODULE_LABELS } from '@/utils/labels'
import { humanizeDatesInText } from '@/utils/dates'
import type { SearchResult } from '@/types'

const router = useRouter()

const open = ref(false)
const query = ref('')
const debouncedQuery = ref('')
const results = ref<SearchResult[]>([])
const loading = ref(false)
const error = ref('')
const activeIndex = ref(-1)
const inputRef = ref<HTMLInputElement | null>(null)
const panelRef = ref<HTMLDivElement | null>(null)
let debounceTimer: ReturnType<typeof setTimeout> | null = null
let requestId = 0

const { activate, deactivate } = useFocusTrap(panelRef, () => open.value)

watch(query, (value) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    debouncedQuery.value = value
  }, 300)
})

watch(debouncedQuery, async (value) => {
  const trimmed = value.trim()
  if (!trimmed) {
    results.value = []
    error.value = ''
    activeIndex.value = -1
    return
  }

  const currentId = ++requestId
  loading.value = true
  error.value = ''
  try {
    const response = await api.search(trimmed)
    if (currentId !== requestId) return
    results.value = response.results
    activeIndex.value = response.results.length ? 0 : -1
  } catch (err) {
    if (currentId !== requestId) return
    error.value = normalizeError(err)
    results.value = []
    activeIndex.value = -1
  } finally {
    if (currentId === requestId) loading.value = false
  }
})

const hasResults = computed(() => results.value.length > 0)
const listboxId = 'global-search-listbox'

function typeLabel(type: string): string {
  const labels: Record<string, string> = {
    employee: MODULE_LABELS.employees,
    event: MODULE_LABELS.events,
    contract: MODULE_LABELS.contracts,
    passport: MODULE_LABELS.passports,
    grade: MODULE_LABELS.grades,
  }
  return labels[type] ?? type
}

function resolveRoute(result: SearchResult): string {
  if (result.route) return result.route
  switch (result.type) {
    case 'employee':
      return '/employees'
    case 'event':
      return '/events'
    case 'contract':
      return '/contracts'
    case 'passport':
      return '/passports'
    case 'grade':
      return '/grades'
    default:
      return '/'
  }
}

function openSearch() {
  open.value = true
  activate()
  window.setTimeout(() => inputRef.value?.focus(), 0)
}

function closeSearch() {
  open.value = false
  deactivate()
  query.value = ''
  debouncedQuery.value = ''
  results.value = []
  activeIndex.value = -1
  error.value = ''
}

function selectResult(result: SearchResult) {
  closeSearch()
  void router.push(resolveRoute(result))
}

function onGlobalShortcut(event: KeyboardEvent) {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    if (open.value) {
      inputRef.value?.focus()
    } else {
      openSearch()
    }
  }
}

function onInputKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeSearch()
    return
  }
  if (!hasResults.value) return

  if (event.key === 'ArrowDown') {
    event.preventDefault()
    activeIndex.value = Math.min(activeIndex.value + 1, results.value.length - 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    activeIndex.value = Math.max(activeIndex.value - 1, 0)
  } else if (event.key === 'Enter' && activeIndex.value >= 0) {
    event.preventDefault()
    const result = results.value[activeIndex.value]
    if (result) selectResult(result)
  }
}

onMounted(() => {
  window.addEventListener('keydown', onGlobalShortcut)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onGlobalShortcut)
  if (debounceTimer) clearTimeout(debounceTimer)
})
</script>

<template>
  <div class="global-search">
    <button type="button" class="search-trigger" aria-label="Открыть поиск" @click="openSearch">
      <span class="search-trigger-label">Поиск...</span>
      <kbd>Ctrl K</kbd>
    </button>

    <div v-if="open" class="search-overlay" @click.self="closeSearch">
      <div ref="panelRef" class="search-panel card" role="dialog" aria-modal="true" aria-label="Глобальный поиск">
        <div class="search-input-wrap">
          <input
            ref="inputRef"
            v-model="query"
            type="search"
            class="search-input"
            placeholder="Поиск сотрудников, событий, договоров..."
            aria-autocomplete="list"
            :aria-controls="listboxId"
            :aria-activedescendant="activeIndex >= 0 ? `search-result-${activeIndex}` : undefined"
            @keydown="onInputKeydown"
          />
          <button type="button" class="btn ghost close-btn" aria-label="Закрыть поиск" @click="closeSearch">
            Esc
          </button>
        </div>

        <div v-if="loading" class="search-state">Поиск...</div>
        <div v-else-if="error" class="search-state error">{{ error }}</div>
        <div v-else-if="debouncedQuery.trim() && !hasResults" class="search-state">Ничего не найдено</div>

        <ul
          v-else-if="hasResults"
          :id="listboxId"
          class="search-results"
          role="listbox"
          aria-label="Результаты поиска"
        >
          <li
            v-for="(result, index) in results"
            :id="`search-result-${index}`"
            :key="`${result.type}-${result.id}`"
            role="option"
            :aria-selected="index === activeIndex"
            :class="{ active: index === activeIndex }"
            @mouseenter="activeIndex = index"
            @click="selectResult(result)"
          >
            <div class="result-main">
              <strong>{{ humanizeDatesInText(result.title) }}</strong>
              <span v-if="result.subtitle" class="result-subtitle">{{ humanizeDatesInText(result.subtitle) }}</span>
            </div>
            <span class="badge">{{ typeLabel(result.type) }}</span>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.global-search {
  position: relative;
}

.search-trigger {
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
  min-width: 220px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.55rem 0.85rem;
  background: var(--surface);
  color: var(--muted);
  text-align: left;
}

.search-trigger-label {
  flex: 1;
}

.search-trigger kbd {
  font-size: 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.1rem 0.35rem;
  color: var(--muted);
  background: var(--bg);
}

.search-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: rgba(15, 23, 42, 0.35);
  display: grid;
  place-items: start center;
  padding: 10vh 1rem 1rem;
}

.search-panel {
  width: min(640px, 100%);
  padding: 0.85rem;
  display: grid;
  gap: 0.75rem;
}

.search-input-wrap {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.search-input {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.75rem 0.9rem;
}

.close-btn {
  white-space: nowrap;
}

.search-state {
  color: var(--muted);
  padding: 0.35rem 0.15rem;
}

.search-state.error {
  color: var(--danger);
}

.search-results {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.35rem;
  max-height: 360px;
  overflow: auto;
}

.search-results li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  padding: 0.65rem 0.75rem;
  border-radius: var(--radius-md);
  cursor: pointer;
}

.search-results li:hover,
.search-results li.active {
  background: var(--accent-soft);
}

.result-main {
  display: grid;
  gap: 0.15rem;
  min-width: 0;
}

.result-subtitle {
  color: var(--muted);
  font-size: 0.85rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
