<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '@/api/client'
import type { TenureRow } from '@/types'
import { formatNumericDate } from '@/utils/dates'

const MILESTONES = ['10', '15', '20'] as const

type MilestoneKey = (typeof MILESTONES)[number]

type AwardFormState = {
  id: number | null
  is_received: boolean
  received_date: string
  milestone_date: string | null
}

const props = defineProps<{
  row: TenureRow | null
}>()

const emit = defineEmits<{
  saved: []
  cancel: []
}>()

const form = ref<Record<MilestoneKey, AwardFormState>>({
  '10': { id: null, is_received: false, received_date: '', milestone_date: null },
  '15': { id: null, is_received: false, received_date: '', milestone_date: null },
  '20': { id: null, is_received: false, received_date: '', milestone_date: null },
})
const submitting = ref(false)
const error = ref('')

function resetForm(row: TenureRow | null) {
  for (const key of MILESTONES) {
    const award = row?.awards[key]
    form.value[key] = {
      id: award?.id ?? null,
      is_received: award?.is_received ?? false,
      received_date: award?.received_date?.slice(0, 10) ?? '',
      milestone_date: award?.milestone_date ?? null,
    }
  }
}

watch(
  () => props.row,
  (row) => resetForm(row),
  { immediate: true },
)

async function submit() {
  if (!props.row) return
  submitting.value = true
  error.value = ''
  try {
    const updates = MILESTONES.filter((key) => form.value[key].id != null).map(async (key) => {
      const award = form.value[key]
      const body: { is_received: boolean; received_date?: string | null } = {
        is_received: award.is_received,
      }
      if (award.is_received) {
        body.received_date = award.received_date || null
      } else {
        body.received_date = null
      }
      await api.updateTenureAward(award.id!, body)
    })
    await Promise.all(updates)
    emit('saved')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Не удалось сохранить награды за стаж'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <form v-if="row" class="form card" @submit.prevent="submit">
    <header class="form-header">
      <div>
        <h3>Награды за стаж: {{ row.full_name ?? 'Сотрудник' }}</h3>
        <p>
          Суммарный стаж: {{ row.tenure_years }} лет · Текущий период:
          {{ row.continuous_tenure_years ?? row.tenure_years }} лет
        </p>
      </div>
      <button class="btn ghost" type="button" @click="emit('cancel')">×</button>
    </header>

    <div class="awards-grid">
      <section v-for="key in MILESTONES" :key="key" class="award-block">
        <h4>{{ key }} лет</h4>
        <p v-if="form[key].milestone_date" class="hint">
          Плановая дата (суммарный стаж): {{ formatNumericDate(form[key].milestone_date) }}
        </p>
        <label class="checkbox">
          <input v-model="form[key].is_received" type="checkbox" :disabled="form[key].id == null" />
          Получено
        </label>
        <label>
          Дата получения
          <input
            v-model="form[key].received_date"
            type="date"
            :disabled="!form[key].is_received || form[key].id == null"
          />
        </label>
      </section>
    </div>

    <div class="actions">
      <button class="btn" type="submit" :disabled="submitting">
        {{ submitting ? 'Сохранение...' : 'Сохранить' }}
      </button>
      <button class="btn ghost" type="button" @click="emit('cancel')">Отмена</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
  </form>
</template>

<style scoped>
.form {
  padding: 1rem;
  display: grid;
  gap: 1rem;
}

.form-header {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 1rem;
}

.form-header h3 {
  margin: 0;
}

.form-header p {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.92rem;
}

.awards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.award-block {
  display: grid;
  gap: 0.65rem;
  padding: 0.85rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.award-block h4 {
  margin: 0;
}

.hint {
  margin: 0;
  color: var(--muted);
  font-size: 0.88rem;
}

.checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

label {
  display: grid;
  gap: 0.35rem;
}

input[type='date'] {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.65rem 0.75rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
}

.error {
  margin: 0;
  color: var(--danger);
}
</style>
