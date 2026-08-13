<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { MODULE_LABELS } from '@/utils/labels'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()

type SettingsTab = 'settings-users' | 'settings-notifications'

const tabs = computed(() => {
  const items: Array<{ name: SettingsTab; label: string }> = []
  if (auth.isAdmin()) {
    items.push({ name: 'settings-users', label: MODULE_LABELS.settingsUsers })
  }
  if (auth.canManageNotifications()) {
    items.push({ name: 'settings-notifications', label: MODULE_LABELS.settingsNotifications })
  }
  return items
})

const activeTab = computed(() => route.name as SettingsTab | undefined)
</script>

<template>
  <section class="card page">
    <header class="page-header">
      <h2>{{ MODULE_LABELS.settings }}</h2>
    </header>

    <div v-if="tabs.length > 1" class="tabs" role="tablist" aria-label="Разделы настроек">
      <RouterLink
        v-for="tab in tabs"
        :id="`settings-tab-${tab.name}`"
        :key="tab.name"
        :to="{ name: tab.name }"
        class="tab"
        role="tab"
        :aria-selected="activeTab === tab.name"
        :aria-controls="`settings-panel-${tab.name}`"
        :tabindex="activeTab === tab.name ? 0 : -1"
        :class="{ active: activeTab === tab.name }"
      >
        {{ tab.label }}
      </RouterLink>
    </div>

    <div class="panel" role="tabpanel" :aria-labelledby="`settings-tab-${activeTab}`">
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
