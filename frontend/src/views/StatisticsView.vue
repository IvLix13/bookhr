<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { api } from '@/api/client'
import type { DashboardStats } from '@/types'
import { defaultStatsPeriod } from '@/utils/dates'
import { labelEventType } from '@/utils/labels'

use([CanvasRenderer, BarChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent])

const loading = ref(true)
const error = ref('')
const stats = ref<DashboardStats | null>(null)
const period = ref(defaultStatsPeriod())

async function loadStats() {
  loading.value = true
  error.value = ''
  try {
    stats.value = await api.stats({ from: period.value.from, to: period.value.to })
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Не удалось загрузить статистику'
    stats.value = null
  } finally {
    loading.value = false
  }
}

onMounted(loadStats)

const eventsStatusChart = computed(() => {
  if (!stats.value) return null
  const data = stats.value.events
  return {
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'pie',
        radius: ['42%', '70%'],
        data: [
          { name: 'Запланировано', value: data.planned },
          { name: 'Просрочено', value: data.overdue },
          { name: 'Выполнено', value: data.completed },
          { name: 'Отменено', value: data.cancelled },
        ],
      },
    ],
  }
})

const eventsMonthlyChart = computed(() => {
  if (!stats.value) return null
  const months = stats.value.events.monthly.map((item) => item.month)
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: 40, right: 16, top: 40, bottom: 24 },
    xAxis: { type: 'category', data: months },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: 'Выполнено', type: 'line', smooth: true, data: stats.value.events.monthly.map((item) => item.completed) },
      { name: 'Просрочено', type: 'bar', data: stats.value.events.monthly.map((item) => item.overdue) },
    ],
  }
})

const eventsTypeChart = computed(() => {
  if (!stats.value) return null
  const entries = Object.entries(stats.value.events.by_type)
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, top: 16, bottom: 24 },
    xAxis: {
      type: 'category',
      data: entries.map(([key]) => labelEventType(key)),
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{ type: 'bar', data: entries.map(([, value]) => value), itemStyle: { color: '#2f6fed' } }],
  }
})

const gradesChart = computed(() => {
  if (!stats.value) return null
  const entries = Object.entries(stats.value.grades.distribution)
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, top: 16, bottom: 24 },
    xAxis: { type: 'category', data: entries.map(([name]) => name) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{ type: 'bar', data: entries.map(([, value]) => value), itemStyle: { color: '#1f8a55' } }],
  }
})

const passportsChart = computed(() => {
  if (!stats.value) return null
  const data = stats.value.passports
  return {
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'pie',
        radius: '68%',
        data: [
          { name: 'В норме', value: data.ok },
          { name: 'Подготовка', value: data.requires_preparation },
          { name: 'Истёк', value: data.expired },
          { name: 'Нет данных', value: data.missing },
        ],
      },
    ],
  }
})

const tenureChart = computed(() => {
  if (!stats.value) return null
  const milestones = ['10', '15', '20']
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: 40, right: 16, top: 40, bottom: 24 },
    xAxis: { type: 'category', data: milestones.map((item) => `${item} лет`) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: 'Получено', type: 'bar', data: milestones.map((item) => stats.value!.tenure.received[item] ?? 0) },
      { name: 'Ожидает', type: 'bar', data: milestones.map((item) => stats.value!.tenure.pending[item] ?? 0) },
    ],
  }
})
</script>

<template>
  <section class="stats-page">
    <header class="card page-header">
      <div>
        <h2>Статистика</h2>
        <p>Операционные показатели по кадровым модулям</p>
      </div>
      <form class="period-form" @submit.prevent="loadStats">
        <label>
          С
          <input v-model="period.from" type="date" required />
        </label>
        <label>
          По
          <input v-model="period.to" type="date" required />
        </label>
        <button class="btn" type="submit" :disabled="loading">Обновить</button>
      </form>
    </header>

    <div v-if="loading" class="card page-state">Загрузка...</div>
    <div v-else-if="error" class="card page-state error">{{ error }}</div>
    <template v-else-if="stats">
      <div class="kpi-grid">
        <article class="card kpi">
          <span>Активные сотрудники</span>
          <strong>{{ stats.employees.active }}</strong>
        </article>
        <article class="card kpi">
          <span>Мероприятия выполнено</span>
          <strong>{{ stats.events.completed }}</strong>
        </article>
        <article class="card kpi">
          <span>Просрочено</span>
          <strong>{{ stats.events.overdue }}</strong>
        </article>
        <article class="card kpi">
          <span>% выполнения</span>
          <strong>{{ stats.events.completion_rate }}%</strong>
        </article>
      </div>

      <div class="module-grid">
        <article class="card module-card">
          <header><h3>Сотрудники</h3></header>
          <ul class="metric-list">
            <li><span>Активные</span><strong>{{ stats.employees.active }}</strong></li>
            <li><span>Приняты за период</span><strong>{{ stats.employees.hired_in_period }}</strong></li>
            <li><span>Уволены за период</span><strong>{{ stats.employees.dismissed_in_period }}</strong></li>
          </ul>
        </article>

        <article class="card module-card">
          <header><h3>Договоры</h3></header>
          <ul class="metric-list">
            <li><span>Активные</span><strong>{{ stats.contracts.active }}</strong></li>
            <li><span>Истёкшие</span><strong>{{ stats.contracts.expired }}</strong></li>
            <li><span>Заканчиваются ≤120 дн.</span><strong>{{ stats.contracts.expiring_120d }}</strong></li>
          </ul>
        </article>

        <article class="card module-card">
          <header><h3>Грейды</h3></header>
          <ul class="metric-list">
            <li><span>Без грейда</span><strong>{{ stats.grades.without_grade }}</strong></li>
            <li><span>Готовы к повышению</span><strong>{{ stats.grades.eligible_now }}</strong></li>
            <li><span>Повышение ≤30 дн.</span><strong>{{ stats.grades.eligible_30d }}</strong></li>
            <li><span>Назначено за период</span><strong>{{ stats.grades.assigned_in_period }}</strong></li>
          </ul>
        </article>

        <article class="card module-card">
          <header><h3>Паспорта</h3></header>
          <ul class="metric-list">
            <li><span>В норме</span><strong>{{ stats.passports.ok }}</strong></li>
            <li><span>Требуют подготовки</span><strong>{{ stats.passports.requires_preparation }}</strong></li>
            <li><span>Истекли</span><strong>{{ stats.passports.expired }}</strong></li>
            <li><span>Истекают ≤90 дн.</span><strong>{{ stats.passports.expiring_90d }}</strong></li>
          </ul>
        </article>
      </div>

      <div class="chart-grid">
        <article class="card chart-card">
          <header><h3>Мероприятия по статусам</h3></header>
          <VChart v-if="eventsStatusChart" class="chart" :option="eventsStatusChart" autoresize />
        </article>
        <article class="card chart-card">
          <header><h3>Динамика мероприятий</h3></header>
          <VChart v-if="eventsMonthlyChart" class="chart" :option="eventsMonthlyChart" autoresize />
        </article>
        <article class="card chart-card">
          <header><h3>Мероприятия по типам</h3></header>
          <VChart v-if="eventsTypeChart" class="chart" :option="eventsTypeChart" autoresize />
        </article>
        <article class="card chart-card">
          <header><h3>Распределение грейдов</h3></header>
          <VChart v-if="gradesChart" class="chart" :option="gradesChart" autoresize />
        </article>
        <article class="card chart-card">
          <header><h3>Паспорта по статусам</h3></header>
          <VChart v-if="passportsChart" class="chart" :option="passportsChart" autoresize />
        </article>
        <article class="card chart-card">
          <header><h3>Поощрения по стажу</h3></header>
          <VChart v-if="tenureChart" class="chart" :option="tenureChart" autoresize />
        </article>
      </div>
    </template>
  </section>
</template>

<style scoped>
.stats-page {
  display: grid;
  gap: 1rem;
}

.label-form {
  display: flex;
  flex-direction: row;
}

.page-header {
  padding: 1rem;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: end;
}

.page-header h2,
.module-card h3,
.chart-card h3 {
  margin: 0;
}

.page-header p {
  margin: 0.35rem 0 0;
  color: var(--muted);
}

.period-form {
  display: flex;
  gap: 0.75rem;
  align-items: end;
  flex-wrap: wrap;
}

.period-form label {
  display: grid;
  gap: 0.35rem;
  font-size: 0.9rem;
}

.period-form input {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.65rem 0.8rem;
}

.page-state {
  padding: 1rem;
}

.page-state.error {
  color: var(--danger);
}

.kpi-grid,
.module-grid,
.chart-grid {
  display: grid;
  gap: 1rem;
}

.kpi-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.module-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.chart-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.kpi,
.module-card,
.chart-card {
  padding: 1rem;
}

.kpi {
  display: grid;
  gap: 0.5rem;
}

.kpi span {
  color: var(--muted);
  font-size: 0.92rem;
}

.kpi strong {
  font-size: 1.8rem;
}

.metric-list {
  list-style: none;
  margin: 0.75rem 0 0;
  padding: 0;
  display: grid;
  gap: 0.55rem;
}

.metric-list li {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}

.chart {
  width: 100%;
  height: 280px;
}

@media (max-width: 1100px) {
  .kpi-grid,
  .module-grid,
  .chart-grid {
    grid-template-columns: 1fr;
  }
}
</style>
