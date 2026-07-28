<script setup lang="ts" generic="T">
import { computed } from 'vue'
import { useDataTable, type ColumnDef } from '@/composables/useDataTable'

const props = withDefaults(
  defineProps<{
    columns: ColumnDef<T>[]
    rows: T[]
    rowKey: keyof T | ((row: T) => string | number)
    searchPlaceholder?: string
    loading?: boolean
    emptyText?: string
  }>(),
  {
    searchPlaceholder: 'Поиск по таблице...',
    loading: false,
    emptyText: 'Нет данных',
  },
)

const rowsRef = computed(() => props.rows)

const {
  search,
  sortKey,
  sortDir,
  columnFilters,
  filteredRows,
  toggleSort,
  setColumnFilter,
  resetFilters,
  hasActiveFilters,
  getDisplayValue,
} = useDataTable(rowsRef, props.columns)

function resolveRowKey(row: T, index: number): string | number {
  if (typeof props.rowKey === 'function') return props.rowKey(row)
  const value = row[props.rowKey]
  return value == null ? index : (value as string | number)
}

function sortIndicator(key: string): string {
  if (sortKey.value !== key) return '↕'
  return sortDir.value === 'asc' ? '↑' : '↓'
}
</script>

<template>
  <div class="data-table">
    <div class="data-table-toolbar">
      <input
        v-model="search"
        type="search"
        class="data-table-search"
        :placeholder="searchPlaceholder"
        aria-label="Поиск по таблице"
      />
      <button
        v-if="hasActiveFilters"
        type="button"
        class="btn ghost data-table-reset"
        @click="resetFilters"
      >
        Сбросить фильтры
      </button>
    </div>

    <div v-if="loading" class="data-table-state">Загрузка...</div>
    <div v-else-if="!filteredRows.length" class="data-table-state">
      {{ hasActiveFilters ? 'Ничего не найдено' : emptyText }}
    </div>

    <div v-else class="table-wrap">
      <table class="table data-table-grid">
        <thead>
          <tr>
            <th
              v-for="column in columns"
              :key="column.key"
              :class="{ sortable: column.sortable !== false }"
            >
              <button
                v-if="column.sortable !== false"
                type="button"
                class="th-button"
                @click="toggleSort(column.key)"
              >
                <span>{{ column.label }}</span>
                <span class="sort-indicator">{{ sortIndicator(column.key) }}</span>
              </button>
              <span v-else>{{ column.label }}</span>
              <input
                v-if="column.filterable !== false"
                :value="columnFilters[column.key] ?? ''"
                type="search"
                class="column-filter"
                :placeholder="`Фильтр: ${column.label}`"
                :aria-label="`Фильтр по столбцу ${column.label}`"
                @input="setColumnFilter(column.key, ($event.target as HTMLInputElement).value)"
              />
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in filteredRows" :key="resolveRowKey(row, index)">
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
        </tbody>
      </table>
    </div>
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
  border-radius: 10px;
  padding: 0.65rem 0.9rem;
}

.data-table-reset {
  white-space: nowrap;
}

.table-wrap {
  overflow: auto;
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
  border-radius: 8px;
  padding: 0.35rem 0.55rem;
  font-size: 0.82rem;
}

.data-table-state {
  color: var(--muted);
  padding: 0.5rem 0;
}
</style>
