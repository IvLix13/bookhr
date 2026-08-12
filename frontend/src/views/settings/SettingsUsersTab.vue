<script setup lang="ts">
import { ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import PageState from '@/components/PageState.vue'
import UserForm from '@/components/settings/UserForm.vue'
import { api } from '@/api/client'
import { useToast } from '@/composables/useToast'
import { useServerTable } from '@/composables/useServerTable'
import type { ColumnDef } from '@/composables/useDataTable'
import type { Paginated, TableQueryState, UserListItem } from '@/types'

const toast = useToast()
const editing = ref<UserListItem | null>(null)
const creating = ref(false)

const table = useServerTable<UserListItem>({
  tableId: 'settings-users',
  fetcher: (params) => api.users(params) as Promise<Paginated<UserListItem>>,
  defaultSort: { key: 'username', direction: 'asc' },
})

const columns: ColumnDef<UserListItem>[] = [
  { key: 'username', label: 'Логин' },
  { key: 'full_name', label: 'ФИО' },
  { key: 'role', label: 'Роль' },
  {
    key: 'auth_source',
    label: 'Источник',
    getValue: (row) => (row.auth_source === 'ldap' ? 'LDAP' : 'Локальный'),
  },
  {
    key: 'is_active',
    label: 'Статус',
    sortable: false,
    filterable: false,
  },
  {
    key: 'is_locked',
    label: 'Блокировка',
    getValue: (row) => (row.is_locked ? 'Заблокирован' : '—'),
  },
  {
    key: 'actions',
    label: '',
    sortable: false,
    filterable: false,
  },
]

function onQueryUpdate(patch: Partial<TableQueryState>) {
  table.setQuery(patch)
}

function startCreate() {
  creating.value = true
  editing.value = null
}

function startEdit(row: UserListItem) {
  editing.value = row
  creating.value = false
}

function cancelForm() {
  editing.value = null
  creating.value = false
}

async function handleSaved() {
  editing.value = null
  creating.value = false
  await table.reload()
  toast.success('Пользователь сохранён')
}

async function toggleActive(row: UserListItem) {
  try {
    await api.updateUser(row.id, { is_active: !row.is_active })
    await table.reload()
    toast.success(row.is_active ? 'Пользователь деактивирован' : 'Пользователь активирован')
  } catch (err) {
    toast.error(err instanceof Error ? err.message : 'Не удалось изменить статус')
  }
}

async function unlockUser(row: UserListItem) {
  try {
    await api.unlockUser(row.id)
    await table.reload()
    toast.success('Блокировка снята')
  } catch (err) {
    toast.error(err instanceof Error ? err.message : 'Не удалось разблокировать')
  }
}
</script>

<template>
  <section class="tab-page">
    <header class="tab-header">
      <div>
        <h3>Пользователи и роли</h3>
        <p class="hint">
          Управление локальными учётными записями и назначением ролей admin, hr, viewer.
          LDAP-пользователи создаются при первом входе.
        </p>
      </div>
      <button v-if="!creating && !editing" class="btn" type="button" @click="startCreate">
        Новый пользователь
      </button>
    </header>

    <UserForm
      v-if="creating || editing"
      :initial="editing"
      @saved="handleSaved"
      @cancel="cancelForm"
    />

    <PageState :error="table.error.value" @retry="table.reload()">
      <DataTable
        mode="server"
        table-id="settings-users"
        :columns="columns"
        :rows="table.rows.value"
        row-key="id"
        :loading="table.loading.value"
        :total="table.total.value"
        :page="table.query.value.page"
        :per-page="table.query.value.per_page"
        :sort-key="table.query.value.sort"
        :sort-dir="table.query.value.direction"
        :search="table.query.value.q"
        :column-filters="table.query.value.columnFilters"
        search-placeholder="Поиск по логину или ФИО..."
        @update:query="onQueryUpdate"
      >
        <template #cell-is_active="{ row }">
          <span :class="row.is_active ? 'badge' : 'badge muted'">
            {{ row.is_active ? 'Активен' : 'Неактивен' }}
          </span>
        </template>
        <template #cell-actions="{ row }">
          <div class="row-actions">
            <button class="btn secondary" type="button" @click="startEdit(row)">Изменить</button>
            <button class="btn ghost" type="button" @click="toggleActive(row)">
              {{ row.is_active ? 'Деактивировать' : 'Активировать' }}
            </button>
            <button
              v-if="row.is_locked"
              class="btn ghost"
              type="button"
              @click="unlockUser(row)"
            >
              Разблокировать
            </button>
          </div>
        </template>
      </DataTable>
    </PageState>
  </section>
</template>

<style scoped>
.tab-page {
  display: grid;
  gap: 1rem;
}

.tab-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  flex-wrap: wrap;
}

.tab-header h3 {
  margin: 0;
}

.hint {
  margin: 0.35rem 0 0;
  color: var(--muted);
  max-width: 42rem;
}

.row-actions {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.badge.muted {
  opacity: 0.75;
}
</style>
