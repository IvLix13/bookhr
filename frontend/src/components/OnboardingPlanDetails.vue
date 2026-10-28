<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { formatShortDate } from '@/utils/dates'
import { cellLabel, stageLabels, stageState } from '@/utils/onboarding'
import type { OnboardingColumn, OnboardingPlan } from '@/types/onboarding'
const props = defineProps<{ plan: OnboardingPlan; columns: OnboardingColumn[]; today: string; editable: boolean }>()
const emit = defineEmits<{ edit: [column: OnboardingColumn] }>()
const query = ref('')
const scroll = ref<HTMLElement | null>(null)
function isStage(c: OnboardingColumn) { return c.field_type === 'stage' || c.field_type === 'checkbox' }
function state(c: OnboardingColumn) { return stageState(c, props.plan.cells[c.id], props.today) }
function label(c: OnboardingColumn) { return isStage(c) ? stageLabels[state(c)] : cellLabel(props.plan, c) }
function planned(c: OnboardingColumn) { return c.field_type === 'stage' && !props.plan.cells[c.id]?.is_not_required ? formatShortDate(props.plan.cells[c.id]?.planned_date) : '—' }
function completed(c: OnboardingColumn) { return c.field_type === 'stage' && state(c) === 'completed' ? formatShortDate(props.plan.cells[c.id]?.completed_date) : '—' }
const visible = computed(() => props.columns.filter(c => [c.title, c.responsible_department, label(c), planned(c), completed(c)].join(' ').toLocaleLowerCase('ru').includes(query.value.trim().toLocaleLowerCase('ru'))))
watch(query, () => { if (scroll.value) scroll.value.scrollTop = 0 })
watch(() => props.plan.id, () => { query.value = '' })
</script>
<template>
  <section class="plan-details" :aria-label="`Этапы: ${plan.full_name}`">
    <div class="details-header"><div><h4>Этапы и данные плана</h4><span aria-live="polite">Найдено: {{ visible.length }} из {{ columns.length }}</span></div><input v-model="query" type="search" aria-label="Поиск по таблице плана" placeholder="Поиск по таблице…" /></div>
    <p v-if="!columns.length">Этапы пока не настроены.</p>
    <div v-else ref="scroll" class="details-scroll" role="region" aria-label="Таблица этапов" tabindex="0">
      <table><thead><tr><th scope="col">Этап / поле</th><th scope="col">Ответственный отдел</th><th scope="col">Плановый срок</th><th scope="col">Выполнено</th><th scope="col">Состояние / значение</th></tr></thead>
        <tbody><tr v-for="column in visible" :key="column.id" :class="{ 'row-completed': isStage(column) && state(column) === 'completed' }">
          <th scope="row">{{ column.title }}</th><td>{{ column.responsible_department || '—' }}</td><td>{{ planned(column) }}</td><td>{{ completed(column) }}</td>
          <td :class="isStage(column) ? state(column).replace('_', '-') : ''"><button v-if="editable" type="button" class="cell-button" :aria-label="`${column.title}, ${plan.full_name}: ${cellLabel(plan, column)}`" @click="emit('edit', column)"><span class="status" :class="isStage(column) ? state(column) : ''">{{ label(column) }}</span></button><span v-else class="status" :class="isStage(column) ? state(column) : ''">{{ label(column) }}</span></td>
        </tr></tbody>
      </table><p v-if="!visible.length" class="empty">Ничего не найдено</p>
    </div>
  </section>
</template>
<style scoped>
.plan-details { display: flex; flex-direction: column; flex: 1; min-height: 0; min-width: 0; padding: 1rem; background: var(--bg); border-radius: var(--radius-lg); }
.details-header { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-bottom: 1rem; flex-shrink: 0; } h4 { margin: 0; } .details-header span { color: var(--muted); font-size: .8rem; }
input { border: 1px solid var(--border); border-radius: var(--radius-md); padding: .65rem .8rem; background: var(--surface); color: var(--text); min-width: 0; }
.details-scroll { overflow: auto; min-height: 0; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface); }
table { width: 100%; min-width: 780px; border-collapse: separate; border-spacing: 0; font-size: .9rem; }
th, td { padding: .85rem .8rem; border-bottom: 1px solid var(--border); text-align: left; overflow-wrap: anywhere; }
thead th { position: sticky; top: 0; background: var(--bg); z-index: 1; color: var(--muted); font-weight: 500; }
thead th:first-child { color: var(--text); background: var(--accent-soft); }
tbody th { width: 28%; font-weight: 600; background: var(--bg); }
td:nth-child(3), td:nth-child(4) { font-variant-numeric: tabular-nums; }
.row-completed > th, .row-completed > td { background: #e2f5e9; }
.cell-button { background: transparent; border: 0; color: inherit; font: inherit; text-align: left; width: 100%; min-height: 32px; padding: 0; white-space: pre-wrap; } .cell-button:hover { text-decoration: underline; }
.status { display: inline-block; padding: .25rem .6rem; border-radius: var(--radius-pill); }
.status.completed { color: #16803c; background: #ccebd8; } .status.overdue { color: #b73535; background: #fdecec; } .status.in_progress { color: #886200; background: #fff4df; } .status.pending, .status.not_required { color: var(--muted); background: var(--bg); }
.empty { padding: 1rem; color: var(--muted); }
@media (max-width: 640px), (max-height: 650px) { .plan-details { flex: none; } .details-scroll { max-height: 55dvh; } }
@media (max-width: 640px) { .details-header { flex-wrap: wrap; } input { width: 100%; } }
</style>
