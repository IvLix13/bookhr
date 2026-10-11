<script setup lang="ts">
import { computed } from 'vue'
import { formatShortDate } from '@/utils/dates'
import { planSummary } from '@/utils/onboarding'
import type { OnboardingColumn, OnboardingPlan } from '@/types/onboarding'

const props = defineProps<{ plan: OnboardingPlan; columns: OnboardingColumn[]; today: string;  }>()
const emit = defineEmits<{ open: [] }>()
const summary = computed(() => planSummary(props.plan, props.columns, props.today))
const segments = computed(() => [
  { key: 'done', value: summary.value.counts.completed },
  { key: 'working', value: summary.value.counts.in_progress },
  { key: 'late', value: summary.value.counts.overdue },
])
</script>

<template>
  <article class="plan-card" :aria-labelledby="`plan-name-${plan.id}`">
    <div class="card-summary">
      <div class="identity">
        <p class="grade">{{ plan.grade || 'Грейд не назначен' }}</p>
        <h3 :id="`plan-name-${plan.id}`">{{ plan.full_name || 'Сотрудник' }}</h3>
        <p class="department">{{ summary.department || 'Отдел не указан' }}</p>
        <span v-if="plan.employment_status === 'dismissed'" class="badge danger">Уволен</span>
      </div>
      <div class="overview">
        <div class="progress-caption"><span>Процент выполнения</span><strong>{{ summary.percent }}%</strong></div>
        <div class="progress-track" role="progressbar" :aria-label="`Выполнение плана: ${plan.full_name}`" :aria-valuenow="summary.percent" aria-valuemin="0" aria-valuemax="100" :aria-valuetext="summary.total ? `Выполнено ${summary.counts.completed} из ${summary.total}` : 'Нет обязательных этапов'">
          <span v-for="segment in segments" :key="segment.key" class="progress-segment" :class="segment.key" :style="{ width: `${summary.total ? segment.value / summary.total * 100 : 0}%` }" />
        </div>
        <div class="overview-grid">
          <div class="facts">
            <p><span>Прибыл:</span> {{ formatShortDate(summary.arrival) }}</p>
            <p><span>Сделано мероприятий:</span> {{ summary.counts.completed }}/{{ summary.total }}</p>
            <p v-if="!summary.total" class="muted">Нет обязательных этапов</p>
            <p v-else-if="summary.next" class="next-stage"><span>Ближайший этап:</span><strong>{{ summary.next.title }}</strong><small v-if="plan.cells[summary.next.id]?.planned_date">Срок: {{ formatShortDate(plan.cells[summary.next.id]?.planned_date) }}</small></p>
            <p v-else class="all-done">Все этапы выполнены</p>
          </div>
          <div class="status-counts" aria-label="Состояния этапов">
            <span class="count-done">Выполнено: <strong>{{ summary.counts.completed }}</strong></span>
            <span class="count-working">В работе: <strong>{{ summary.counts.in_progress }}</strong></span>
            <span class="count-late">Просрочено: <strong>{{ summary.counts.overdue }}</strong></span>
            <span class="count-pending">Не начато: <strong>{{ summary.counts.pending }}</strong></span>
          </div>
        </div>
        <div class="summary-footer">
          <p class="curator"><span>Куратор:</span> {{ plan.curator_name || 'Не назначен' }}</p>
          <button type="button" class="btn secondary expand-button" aria-haspopup="dialog" @click="emit('open')">Открыть план</button>
        </div>
      </div>
    </div>

  </article>
</template>

<style scoped>
.plan-card { border: 1px solid var(--border); border-radius: 18px; overflow: hidden; background: var(--surface); }
.card-summary { display: grid; grid-template-columns: minmax(190px, 25%) minmax(0, 1fr); gap: 2rem; padding: 1.4rem 1.5rem; }
.identity, .overview { min-width: 0; }
.grade { margin: 0 0 .4rem; color: var(--muted); font-size: .95rem; }
h3 { margin: 0; font-size: clamp(1.25rem, 1.6vw, 1.9rem); line-height: 1.3; overflow-wrap: anywhere; }
.department { color: var(--muted); margin: .7rem 0 0; overflow-wrap: anywhere; }
.progress-caption { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-bottom: .6rem; font-size: .9rem; }
.progress-caption span { color: var(--muted); } .progress-caption strong { font-size: 1rem; font-variant-numeric: tabular-nums; }
.progress-track { display: flex; height: 16px; background: var(--border); border-radius: 99px; overflow: hidden; }
.progress-segment { flex: 0 0 auto; } .progress-segment.done { background: #1fa66a; } .progress-segment.working { background: #e8b838; } .progress-segment.late { background: #dc6262; }
.overview-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(200px, 1fr); gap: 1.25rem; margin-top: .85rem; }
p { line-height: 1.5; } .facts p { margin: .2rem 0; font-size: .9rem; } .facts p > span, .curator > span { color: var(--muted); }
.next-stage strong, .next-stage small { display: block; overflow-wrap: anywhere; } .next-stage strong { font-weight: 500; } .next-stage small { color: var(--muted); }
.status-counts { display: flex; flex-wrap: wrap; gap: .5rem 1.1rem; align-content: start; justify-content: flex-end; font-size: .85rem; }
.status-counts > span { white-space: nowrap; } .count-done, .all-done { color: #16803c; } .count-working { color: #886200; } .count-late { color: #b73535; } .count-pending, .muted { color: var(--muted); }
.summary-footer { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: .75rem; margin-top: .8rem; }
.curator { margin: 0; font-size: .9rem; flex: 1; overflow-wrap: anywhere; } .expand-button { font-size: .85rem; padding: .5rem .8rem; }
@media (max-width: 1000px) { .card-summary { gap: 1.25rem; grid-template-columns: minmax(170px, 28%) minmax(0, 1fr); } .overview-grid { grid-template-columns: 1fr; gap: .6rem; } .status-counts { justify-content: flex-start; } }
@media (max-width: 640px) { .card-summary { grid-template-columns: 1fr; padding: 1rem; gap: 1rem; } .summary-footer { align-items: flex-start; } .curator { flex-basis: 100%; } }
</style>
