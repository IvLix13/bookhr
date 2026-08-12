<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { MODULE_LABELS } from '@/utils/labels'

const route = useRoute()

type ImportTab = 'import-employees' | 'import-rewards'

const tabs: Array<{ name: ImportTab; label: string }> = [
  { name: 'import-employees', label: 'Общая таблица' },
  { name: 'import-rewards', label: MODULE_LABELS.rewards },
]

const activeTab = computed(() => route.name as ImportTab | undefined)
</script>

<template>
  <section class="card page">
    <header class="page-header">
      <h2>Импорт из Excel</h2>
    </header>

    <div class="tabs" role="tablist" aria-label="Разделы импорта">
      <RouterLink
        v-for="tab in tabs"
        :id="`import-tab-${tab.name}`"
        :key="tab.name"
        :to="{ name: tab.name }"
        class="tab"
        role="tab"
        :aria-selected="activeTab === tab.name"
        :aria-controls="`import-panel-${tab.name}`"
        :tabindex="activeTab === tab.name ? 0 : -1"
        :class="{ active: activeTab === tab.name }"
      >
        {{ tab.label }}
      </RouterLink>
    </div>

    <div class="panel" role="tabpanel" :aria-labelledby="`import-tab-${activeTab}`">
      <RouterView />
    </div>
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

.tabs {
  display: flex;
  gap: 0.35rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.65rem;
  flex-wrap: wrap;
}

.tab {
  border: none;
  background: transparent;
  color: var(--muted);
  padding: 0.45rem 0.75rem;
  border-radius: 8px;
  font-weight: 600;
  text-decoration: none;
  transition: background var(--transition), color var(--transition);
}

.tab:hover {
  background: var(--bg);
  color: var(--text);
}

.tab.active {
  background: var(--accent-soft);
  color: var(--accent);
}
</style>
