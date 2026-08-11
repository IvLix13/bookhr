<script setup lang="ts">
import { computed } from 'vue'
import { labelImportStatus } from '@/utils/labels'
import type { ImportJob } from '@/types'

const props = defineProps<{
  job: ImportJob
}>()

const summaryEntries = computed(() => {
  if (!props.job.summary) return []
  return Object.entries(props.job.summary)
})
</script>

<template>
  <section class="import-summary">
    <div class="summary-header">
      <div>
        <h3>{{ job.filename }}</h3>
        <p>Статус: {{ labelImportStatus(job.status) }}</p>
        <p v-if="job.created_at" class="meta">Загружен: {{ job.created_at }}</p>
      </div>
      <span class="badge">{{ job.rows.length }} строк</span>
    </div>

    <dl v-if="summaryEntries.length" class="summary-grid">
      <template v-for="[key, value] in summaryEntries" :key="key">
        <dt>{{ key }}</dt>
        <dd>{{ value }}</dd>
      </template>
    </dl>
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
</style>
