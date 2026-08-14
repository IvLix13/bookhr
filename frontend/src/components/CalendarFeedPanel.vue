<script setup lang="ts">
import { ref } from 'vue'
import AttentionPanel from '@/components/AttentionPanel.vue'
import UpcomingPanel from '@/components/UpcomingPanel.vue'
import type { EventItem } from '@/types'

defineProps<{
  events: EventItem[]
  loading?: boolean
}>()

const emit = defineEmits<{
  changed: []
}>()

type FeedTab = 'attention' | 'upcoming'

const activeTab = ref<FeedTab>('attention')
const attentionPanel = ref<InstanceType<typeof AttentionPanel> | null>(null)

function onChanged() {
  emit('changed')
}

/** Both feeds share the same events, so a change in one has to refresh both. */
async function reloadAttention() {
  await attentionPanel.value?.reload()
}

defineExpose({ reloadAttention })

function selectTab(tab: FeedTab) {
  activeTab.value = tab
}

function tabLabel(tab: FeedTab): string {
  switch (tab) {
    case 'attention':
      return 'Требует внимания'
    case 'upcoming':
      return 'Ближайшие события'
    default: {
      const _exhaustive: never = tab
      return _exhaustive
    }
  }
}
</script>

<template>
  <section class="feed card">
    <div class="tabs" role="tablist" aria-label="Лента календаря">
      <button
        v-for="tab in (['attention', 'upcoming'] as const)"
        :id="`feed-tab-${tab}`"
        :key="tab"
        type="button"
        class="tab"
        role="tab"
        :aria-selected="activeTab === tab"
        :aria-controls="`feed-panel-${tab}`"
        :tabindex="activeTab === tab ? 0 : -1"
        :class="{ active: activeTab === tab }"
        @click="selectTab(tab)"
      >
        {{ tabLabel(tab) }}
      </button>
    </div>

    <div
      id="feed-panel-attention"
      class="panel"
      role="tabpanel"
      aria-labelledby="feed-tab-attention"
      :hidden="activeTab !== 'attention'"
    >
      <AttentionPanel ref="attentionPanel" embedded @changed="onChanged" />
    </div>

    <div
      id="feed-panel-upcoming"
      class="panel"
      role="tabpanel"
      aria-labelledby="feed-tab-upcoming"
      :hidden="activeTab !== 'upcoming'"
    >
      <UpcomingPanel embedded :events="events" :loading="loading" @changed="onChanged" />
    </div>
  </section>
</template>

<style scoped>
.feed {
  padding: 1rem 1.2rem;
}

.tabs {
  display: flex;
  gap: 0.35rem;
  margin-bottom: 0.85rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.65rem;
}

.tab {
  border: none;
  background: transparent;
  color: var(--muted);
  padding: 0.45rem 0.75rem;
  border-radius: 8px;
  font-weight: 600;
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

.panel[hidden] {
  display: none;
}
</style>
