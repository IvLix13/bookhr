<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import DataTable from '@/components/DataTable.vue'
import PageState from '@/components/PageState.vue'
import { api, type AttestationRow } from '@/api/client'
import { useServerTable } from '@/composables/useServerTable'
import type { ColumnDef } from '@/composables/useDataTable'
import type { Paginated, TableQueryState } from '@/types'
import { formatShortDate } from '@/utils/dates'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const editing = ref<AttestationRow | null>(null)
const modalOpen = ref(false)
const dateValue = ref('')
const saving = ref(false)
const saveError = ref<string | null>(null)

const table = useServerTable<AttestationRow>({
  tableId: 'attestations',
  schemaVersion: 1,
  fetcher: (params) => api.attestations(params) as Promise<Paginated<AttestationRow>>,
  defaultSort: { key: 'full_name', direction: 'asc' },
})

const columns: ColumnDef<AttestationRow>[] = [
  { key: 'full_name', label: 'ФИО сотрудника' },
  {
    key: 'attestation_date',
    label: 'Дата проведения',
    getValue: (row) => row.attestation_date,
    format: (value) => formatShortDate(value as string | null),
  },
]

const pageHint = computed(
  () => 'Дата аттестации проставляется HR вручную. В таблице отображаются активные сотрудники.',
)

function onQueryUpdate(patch: Partial<TableQueryState>) {
  table.setQuery(patch)
}

function startEdit(row: AttestationRow) {
  if (!auth.canEdit()) return
  editing.value = row
  dateValue.value = row.attestation_date ?? ''
  saveError.value = null
  modalOpen.value = true
}

function closeModal() {
  if (saving.value) return
  modalOpen.value = false
  editing.value = null
  dateValue.value = ''
  saveError.value = null
}

async function save() {
  if (!editing.value || saving.value) return
  saving.value = true
  saveError.value = null
  try {
    await api.updateAttestation(editing.value.employment_id, dateValue.value || null)
    saving.value = false
    closeModal()
    await table.reload()
  } catch (error) {
    saveError.value = error instanceof Error ? error.message : 'Не удалось сохранить дату'
  } finally {
    saving.value = false
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && modalOpen.value) closeModal()
}

window.addEventListener('keydown', onKeydown)
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <section class="card page">
    <header class="page-header">
      <div>
        <h2>Аттестация</h2>
        <p class="hint">{{ pageHint }}</p>
      </div>
    </header>

    <PageState
      :loading="table.loading.value"
      :refreshing="table.refreshing.value"
      :error="table.error.value"
      :has-data="table.rows.value.length > 0"
      @retry="table.reload()"
    >
      <DataTable
        mode="server"
        table-id="attestations"
        :columns="columns"
        :rows="table.rows.value"
        :row-key="(row) => row.employment_id"
        :row-clickable="auth.canEdit()"
        :loading="table.loading.value"
        :total="table.total.value"
        :page="table.query.value.page"
        :per-page="table.query.value.per_page"
        :sort-key="table.query.value.sort"
        :sort-dir="table.query.value.direction"
        :search="table.query.value.q"
        :column-filters="table.query.value.columnFilters"
        default-sort-key="full_name"
        default-sort-dir="asc"
        search-placeholder="Поиск по ФИО..."
        @update:query="onQueryUpdate"
        @row-click="startEdit"
      />
    </PageState>

    <Teleport to="body">
      <div v-if="modalOpen && editing" class="overlay" @click.self="closeModal">
        <section class="card modal" role="dialog" aria-modal="true" aria-label="Дата аттестации">
          <header class="modal-header">
            <div>
              <h3>Дата аттестации</h3>
              <p>{{ editing.full_name }}</p>
            </div>
            <button class="btn ghost" type="button" aria-label="Закрыть" @click="closeModal">×</button>
          </header>

          <label class="field">
            <span>Дата проведения</span>
            <input v-model="dateValue" type="date" :disabled="saving" />
          </label>

          <p v-if="saveError" class="error-text">{{ saveError }}</p>

          <footer class="actions">
            <button class="btn secondary" type="button" :disabled="saving" @click="closeModal">Отмена</button>
            <button class="btn" type="button" :disabled="saving" @click="save">
              {{ saving ? 'Сохранение…' : 'Сохранить' }}
            </button>
          </footer>
        </section>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.page {
  padding: 1rem;
  display: grid;
  gap: 1rem;
}

.page-header h2 {
  margin: 0;
}

.hint {
  margin: 0.35rem 0 0;
  color: var(--muted);
  max-width: 52rem;
}

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
  width: min(520px, 100%);
  padding: 1rem;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
}

.modal-header h3 {
  margin: 0;
}

.modal-header p {
  margin: 0.35rem 0 0;
  color: var(--muted);
}

.field {
  display: grid;
  gap: 0.4rem;
}

.field input {
  width: 100%;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
}

.error-text {
  color: var(--danger);
  margin: 0.75rem 0 0;
}
</style>
