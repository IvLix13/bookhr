<script setup lang="ts" generic="T">
import { computed, nextTick, ref, watch } from 'vue'
import { useDataTable, type ColumnDef, type SortDirection } from '@/composables/useDataTable'
import type { TableQueryState } from '@/types'

const props = withDefaults(
  defineProps<{
    mode?: 'client' | 'server'
    columns: ColumnDef<T>[]
    rows: T[]
    rowKey: keyof T | ((row: T) => string | number)
    tableId?: string
    searchPlaceholder?: string
    loading?: boolean
    emptyText?: string
    paginate?: boolean
    perPage?: number
    page?: number
    total?: number
    sortKey?: string | null
    sortDir?: SortDirection
    search?: string
    columnFilters?: Record<string, string>
    perPageOptions?: number[]
    highlightRowKey?: string | number | null
    rowClass?: (row: T) => string | Record<string, boolean> | undefined
    rowAttrs?: (row: T) => Record<string, string | number | undefined>
    rowClickable?: boolean
  }>(),
  {
    mode: 'client',
    searchPlaceholder: 'Поиск по таблице...',
    loading: false,
    emptyText: 'Нет данных',
    paginate: false,
    perPage: 25,
    page: 1,
    total: 0,
    sortKey: null,
    sortDir: 'asc',
    search: '',
    columnFilters: () => ({}),
    perPageOptions: () => [10, 25, 50, 100],
    rowClickable: false,
  },
)

const emit = defineEmits<{
  'update:query': [query: Partial<TableQueryState>]
  'row-click': [row: T]
}>()

const rowsRef = computed(() => props.rows)
const isServer = computed(() => props.mode === 'server')

const clientTable = useDataTable(rowsRef, props.columns, {
  paginate: props.mode === 'client' && props.paginate,
  perPage: props.perPage,
})

const localSearch = ref(props.search)
const localColumnFilters = ref<Record<string, string>>({ ...props.columnFilters })

watch(
  () => props.search,
  (value) => {
    localSearch.value = value
  },
)

watch(
  () => props.columnFilters,
  (value) => {
    localColumnFilters.value = { ...value }
  },
  { deep: true },
)

const displayRows = computed(() =>
  isServer.value ? props.rows : clientTable.paginatedRows.value,
)

const displayTotal = computed(() =>
  isServer.value ? props.total : clientTable.totalFiltered.value,
)

const displayPage = computed(() => (isServer.value ? props.page : clientTable.page.value))

const displayPerPage = computed(() =>
  isServer.value ? props.perPage : clientTable.perPage.value,
)

const displaySortKey = computed(() =>
  isServer.value ? props.sortKey : clientTable.sortKey.value,
)

const displaySortDir = computed(() =>
  isServer.value ? props.sortDir : clientTable.sortDir.value,
)

const displayPages = computed(() => {
  if (isServer.value) {
    return Math.max(1, Math.ceil(props.total / Math.max(props.perPage, 1)))
  }
  return clientTable.totalPages.value
})

const hasActiveFilters = computed(() => {
  if (isServer.value) {
    if (props.search.trim()) return true
    return Object.values(props.columnFilters).some((value) => value.trim())
  }
  return clientTable.hasActiveFilters.value
})

const showEmpty = computed(
  () => !props.loading && !displayRows.value.length,
)

function resolveRowKey(row: T, index: number): string | number {
  if (typeof props.rowKey === 'function') return props.rowKey(row)
  const value = row[props.rowKey]
  return value == null ? index : (value as string | number)
}

function sortIndicator(key: string): string {
  if (displaySortKey.value !== key) return '↕'
  return displaySortDir.value === 'asc' ? '↑' : '↓'
}

function ariaSortValue(key: string): 'ascending' | 'descending' | 'none' {
  if (displaySortKey.value !== key) return 'none'
  return displaySortDir.value === 'asc' ? 'ascending' : 'descending'
}

function emitQuery(patch: Partial<TableQueryState>) {
  emit('update:query', patch)
}

function onRowClick(row: T) {
  if (!props.rowClickable) return
  emit('row-click', row)
}

function onSearchInput(value: string) {
  localSearch.value = value
  if (isServer.value) {
    emitQuery({ q: value, page: 1 })
    return
  }
  clientTable.search.value = value
}

function onToggleSort(key: string) {
  if (isServer.value) {
    if (props.sortKey === key) {
      emitQuery({
        direction: props.sortDir === 'asc' ? 'desc' : 'asc',
        page: 1,
      })
    } else {
      emitQuery({
        sort: key,
        direction: 'asc',
        page: 1,
      })
    }
    return
  }
  clientTable.toggleSort(key)
}

function onColumnFilter(key: string, value: string) {
  localColumnFilters.value = { ...localColumnFilters.value, [key]: value }
  if (isServer.value) {
    emitQuery({
      columnFilters: { ...localColumnFilters.value },
      page: 1,
    })
    return
  }
  clientTable.setColumnFilter(key, value)
}

function onResetFilters() {
  localSearch.value = ''
  localColumnFilters.value = {}
  if (isServer.value) {
    emitQuery({
      q: '',
      sort: null,
      direction: 'asc',
      columnFilters: {},
      page: 1,
    })
    return
  }
  clientTable.resetFilters()
}

function onPageChange(nextPage: number) {
  const page = Math.min(Math.max(1, nextPage), displayPages.value)
  if (isServer.value) {
    emitQuery({ page })
    return
  }
  clientTable.setPage(page)
}

function onPerPageChange(nextPerPage: number) {
  if (isServer.value) {
    emitQuery({ per_page: nextPerPage, page: 1 })
    return
  }
  clientTable.setPerPage(nextPerPage)
}

function getDisplayValue(row: T, column: ColumnDef<T>): string {
  return clientTable.getDisplayValue(row, column)
}

const showPaginator = computed(
  () => (isServer.value || props.paginate) && displayTotal.value > 0,
)

const rangeStart = computed(() => {
  if (!displayTotal.value) return 0
  return (displayPage.value - 1) * displayPerPage.value + 1
})

const rangeEnd = computed(() =>
  Math.min(displayPage.value * displayPerPage.value, displayTotal.value),
)

const tableWrapRef = ref<HTMLElement | null>(null)

function isHighlighted(row: T, index: number): boolean {
  if (props.highlightRowKey == null) return false
  return resolveRowKey(row, index) === props.highlightRowKey
}

watch(
  () => [props.highlightRowKey, displayRows.value.length, props.loading] as const,
  async ([highlightKey, rowCount, loading]) => {
    if (highlightKey == null || loading || !rowCount) return
    await nextTick()
    const row = tableWrapRef.value?.querySelector('.data-table-row-highlight')
    row?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  },
)
</script>

<template>
  <div class="data-table" :data-table-id="tableId">
    <div class="data-table-toolbar">
      <input
        :value="isServer ? localSearch : clientTable.search.value"
        type="search"
        class="data-table-search"
        :placeholder="searchPlaceholder"
        aria-label="Поиск по таблице"
        @input="onSearchInput(($event.target as HTMLInputElement).value)"
      />
      <button
        v-if="hasActiveFilters"
        type="button"
        class="btn ghost data-table-reset"
        @click="onResetFilters"
      >
        Сбросить фильтры
      </button>
    </div>

    <div v-if="loading" class="data-table-state">
      <span class="spinner" aria-hidden="true"></span> Загрузка...
    </div>
    <div v-else-if="showEmpty" class="data-table-state">
      {{ hasActiveFilters ? 'Ничего не найдено' : emptyText }}
    </div>

    <div v-else ref="tableWrapRef" class="table-wrap">
      <table class="table data-table-grid">
        <thead class="data-table-head">
          <tr>
            <th
              v-for="column in columns"
              :key="column.key"
              :class="{ sortable: column.sortable !== false }"
              :aria-sort="column.sortable !== false ? ariaSortValue(column.key) : undefined"
            >
              <button
                v-if="column.sortable !== false"
                type="button"
                class="th-button"
                @click="onToggleSort(column.key)"
              >
                <span>{{ column.label }}</span>
                <span class="sort-indicator">{{ sortIndicator(column.key) }}</span>
              </button>
              <span v-else>{{ column.label }}</span>
              <input
                v-if="column.filterable !== false"
                :value="
                  isServer
                    ? (localColumnFilters[column.key] ?? '')
                    : (clientTable.columnFilters.value[column.key] ?? '')
                "
                type="search"
                class="column-filter"
                :placeholder="`Фильтр: ${column.label}`"
                :aria-label="`Фильтр по столбцу ${column.label}`"
                @input="onColumnFilter(column.key, ($event.target as HTMLInputElement).value)"
              />
            </th>
          </tr>
        </thead>
        <TransitionGroup tag="tbody" name="row">
          <tr
            v-for="(row, index) in displayRows"
            :key="resolveRowKey(row, index)"
            class="data-table-row"
            :class="[
              rowClass?.(row),
              {
                'data-table-row-highlight': isHighlighted(row, index),
                'data-table-row-clickable': rowClickable,
              },
            ]"
            v-bind="rowAttrs?.(row)"
            @click="onRowClick(row)"
          >
            <td v-for="column in columns" :key="column.key">
              <slot
                :name="`cell-${column.key}`"
                :row="row"
                :value="column.getValue ? column.getValue(row) : (row as Record<string, unknown>)[column.key]"
                :display="getDisplayValue(row, column)"
              >
                {{ getDisplayValue(row, column) }}
              </slot>
            </td>
          </tr>
        </TransitionGroup>
      </table>
    </div>

    <footer v-if="showPaginator" class="data-table-footer">
      <div class="data-table-range">
        {{ rangeStart }}–{{ rangeEnd }} из {{ displayTotal }}
      </div>
      <div class="data-table-pagination">
        <button
          type="button"
          class="btn ghost page-btn"
          :disabled="displayPage <= 1"
          aria-label="Предыдущая страница"
          @click="onPageChange(displayPage - 1)"
        >
          ←
        </button>
        <span class="page-indicator">{{ displayPage }} / {{ displayPages }}</span>
        <button
          type="button"
          class="btn ghost page-btn"
          :disabled="displayPage >= displayPages"
          aria-label="Следующая страница"
          @click="onPageChange(displayPage + 1)"
        >
          →
        </button>
      </div>
      <label class="per-page">
        <span>На странице</span>
        <select
          :value="displayPerPage"
          aria-label="Количество строк на странице"
          @change="onPerPageChange(Number(($event.target as HTMLSelectElement).value))"
        >
          <option v-for="option in perPageOptions" :key="option" :value="option">
            {{ option }}
          </option>
        </select>
      </label>
    </footer>
  </div>
</template>

<style scoped>
.data-table {
  display: grid;
  gap: 0.75rem;
}

.data-table-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}

.data-table-search {
  flex: 1 1 240px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.65rem 0.9rem;
}

.data-table-reset {
  white-space: nowrap;
}

.table-wrap {
  overflow: auto;
  max-height: min(70vh, 720px);
}

.data-table-head {
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--surface);
}

.data-table-head th {
  box-shadow: inset 0 -1px 0 var(--border);
}

.data-table-grid th {
  vertical-align: top;
}

.th-button {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border: none;
  background: transparent;
  padding: 0;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.sort-indicator {
  color: var(--muted);
  font-size: 0.85rem;
}

.column-filter {
  display: block;
  width: 100%;
  margin-top: 0.45rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.35rem 0.55rem;
  font-size: 0.82rem;
}

.data-table-state {
  color: var(--muted);
  padding: 0.5rem 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  animation: fade var(--transition) var(--ease-out) both;
}

@keyframes fade {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.row-enter-active {
  transition: opacity var(--transition-slow), transform var(--transition-slow);
}

.row-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.row-move {
  transition: transform var(--transition-slow);
}

.data-table-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid var(--border);
  padding-top: 0.75rem;
}

.data-table-range {
  color: var(--muted);
  font-size: 0.9rem;
}

.data-table-pagination {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.page-btn {
  min-width: 2.25rem;
  padding-inline: 0.65rem;
}

.page-indicator {
  font-size: 0.9rem;
  min-width: 4.5rem;
  text-align: center;
}

.per-page {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  color: var(--muted);
}

.per-page select {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.35rem 0.55rem;
  background: var(--surface);
}

.data-table-row-clickable {
  cursor: pointer;
}

.data-table-row-clickable:hover {
  background: var(--bg);
}

.data-table-row-highlight {
  background: var(--accent-soft);
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}
</style>
