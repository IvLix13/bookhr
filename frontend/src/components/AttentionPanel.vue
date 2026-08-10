<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import PageState from '@/components/PageState.vue'
import { api } from '@/api/client'
import { useAsyncResource } from '@/composables/useAsyncResource'
import type { AttentionItem, AttentionSummary } from '@/types'

const resource = useAsyncResource<AttentionSummary>()

const summary = computed(() => resource.data.value)
const counts = computed(() => summary.value?.counts ?? {})
const items = computed(() => summary.value?.items ?? [])

const categoryLabels: Record<string, string> = {
  events: 'События',
  contracts: 'Договоры',
  passports: 'Паспорта',
  grades: 'Грейды',
  tenure: 'Стаж',
}

function categoryLabel(key: string): string {
  return categoryLabels[key] ?? key
}

function severityClass(severity: AttentionItem['severity']): string {
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

async function loadAttention() {
  await resource.execute(() => api.attention())
}

onMounted(() => {
  void loadAttention()
})
</script>

<template>
  <section class="attention card">
    <header class="attention-header">
      <div>
        <h3>Требует внимания</h3>
        <p v-if="summary">Всего: {{ summary.total }}</p>
      </div>
      <button
        type="button"
        class="btn ghost"
        :disabled="resource.isBusy()"
        @click="loadAttention()"
      >
        Обновить
      </button>
    </header>

    <PageState
      :loading="resource.isLoading()"
      :refreshing="resource.isRefreshing()"
      :error="resource.error.value"
      :empty="!resource.isBusy() && !items.length"
      empty-text="Нет срочных задач"
      @retry="loadAttention()"
    >
      <div v-if="Object.keys(counts).length" class="attention-counts">
        <div v-for="(count, key) in counts" :key="key" class="count-chip">
          <span class="count-label">{{ categoryLabel(String(key)) }}</span>
          <strong>{{ count }}</strong>
        </div>
      </div>

      <ul class="attention-list">
        <li v-for="item in items" :key="item.id" class="attention-item">
          <component
            :is="item.route ? RouterLink : 'div'"
            :to="item.route ?? undefined"
            class="attention-link"
            :class="severityClass(item.severity)"
          >
            <div class="attention-main">
              <strong>{{ item.title }}</strong>
              <p v-if="item.subtitle">{{ item.subtitle }}</p>
            </div>
            <div class="attention-meta">
              <span class="badge" :class="severityClass(item.severity)">{{ categoryLabel(item.category) }}</span>
              <span v-if="item.count != null" class="count">{{ item.count }}</span>
            </div>
          </component>
        </li>
      </ul>
    </PageState>
  </section>
</template>

<style scoped>
.attention {
  padding: 1rem 1.2rem;
}

.attention-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 0.75rem;
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
}

.count-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.25rem 0.65rem;
  font-size: 0.85rem;
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
}

.attention-link {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 12px;
  transition: background var(--transition);
}

.attention-link:hover {
  background: var(--bg);
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

.count {
  font-size: 0.85rem;
  color: var(--muted);
}
</style>
