<script setup lang="ts">
import { computed } from 'vue'
import {
  labelImportSkipReason,
  labelImportStatus,
  labelImportSummaryKey,
} from '@/utils/labels'
import type { ImportJob } from '@/types'
import { formatShortDate } from '@/utils/dates'

const props = defineProps<{
  job: ImportJob
}>()

const summaryEntries = computed(() => {
  if (!props.job.summary) return []
  return Object.entries(props.job.summary).filter(
    ([key, value]) =>
      key !== 'skipped_reasons' && key !== 'unknown_grades' && typeof value === 'number',
  ) as Array<[string, number]>
})

const skipReasons = computed(() => {
  const reasons = props.job.summary?.skipped_reasons
  if (!reasons) return []
  return Object.entries(reasons)
})
</script>

<template>
  <section class="import-summary">
    <div class="summary-header">
      <div>
        <h3>{{ job.filename }}</h3>
        <p>Статус: {{ labelImportStatus(job.status) }}</p>
        <p v-if="job.created_at" class="meta">Загружен: {{ formatShortDate(job.created_at) }}</p>
        <p v-if="job.error_message" class="error">{{ job.error_message }}</p>
      </div>
      <span class="badge">{{ job.rows.length }} строк</span>
    </div>

    <dl v-if="summaryEntries.length" class="summary-grid">
      <template v-for="[key, value] in summaryEntries" :key="key">
        <dt>{{ labelImportSummaryKey(key) }}</dt>
        <dd>{{ value }}</dd>
      </template>
    </dl>

    <ul v-if="skipReasons.length" class="skip-reasons">
      <li v-for="[reason, count] in skipReasons" :key="reason">
        {{ labelImportSkipReason(reason) }}: {{ count }}
      </li>
    </ul>
  </section>
</template>

<style scoped>
.import-summary {
  display: grid;
  gap: 0.85rem;
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg);
}

.summary-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.summary-header h3 {
  margin: 0;
  font-size: 1rem;
}

.summary-header p {
  margin: 0.25rem 0 0;
}

.meta {
  color: var(--muted);
  font-size: 0.9rem;
}

.error {
  color: var(--danger);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.65rem 1rem;
  margin: 0;
}

.summary-grid dt {
  color: var(--muted);
  font-size: 0.85rem;
}

.summary-grid dd {
  margin: 0.15rem 0 0;
  font-weight: 600;
}

.skip-reasons {
  margin: 0;
  padding-left: 1.1rem;
  color: var(--muted);
  font-size: 0.9rem;
}
</style>
