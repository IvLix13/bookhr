<script setup lang="ts">
import NavItem from '@/components/NavItem.vue'
import {
  IconAward,
  IconCalendar,
  IconContract,
  IconEmployees,
  IconEvent,
  IconGrade,
  IconImport,
  IconPassport,
  IconSettings,
  IconStats,
  IconTable,
} from '@/components/icons'
import IconCake from '@/components/icons/IconCake.vue'
import { MODULE_LABELS } from '@/utils/labels'
import { useAuthStore } from '@/stores/auth'
import { useRoute } from 'vue-router'

defineProps<{
  expanded: boolean
}>()

defineEmits<{
  'update:expanded': [value: boolean]
  toggle: []
}>()

const route = useRoute()
const auth = useAuthStore()
</script>

<template>
  <aside
    class="sidebar card"
    :class="{ expanded }"
    aria-label="Основная навигация"
  >
    <div class="brand-div">
      <div class="brand">У</div>
      <span v-if="expanded" class="brand-label">Учет кадровых событий</span>
    </div>

    <nav id="sidebar-nav" class="sidebar-nav">
      <NavItem
        name="calendar"
        :label="MODULE_LABELS.calendar"
        :expanded="expanded"
        :active="route.name === 'calendar'"
      >
        <IconCalendar />
      </NavItem>
      <NavItem
        name="statistics"
        :label="MODULE_LABELS.statistics"
        :expanded="expanded"
        :active="route.name === 'statistics'"
      >
        <IconStats />
      </NavItem>
      <NavItem
        name="employees"
        :label="MODULE_LABELS.employees"
        :expanded="expanded"
        :active="route.name === 'employees'"
      >
        <IconTable />
      </NavItem>
      <NavItem
        name="import"
        :label="MODULE_LABELS.import"
        :expanded="expanded"
        :active="route.name === 'import'"
      >
        <IconImport />
      </NavItem>
      <NavItem
        name="event-create"
        :label="MODULE_LABELS.eventCreate"
        :expanded="expanded"
        :active="route.name === 'event-create'"
      >
        <IconEvent />
      </NavItem>
      <NavItem
        name="contracts"
        :label="MODULE_LABELS.contracts"
        :expanded="expanded"
        :active="route.name === 'contracts'"
      >
        <IconContract />
      </NavItem>
      <NavItem
        name="grades"
        :label="MODULE_LABELS.grades"
        :expanded="expanded"
        :active="route.name === 'grades' || route.name === 'grade-catalog'"
      >
        <IconGrade />
      </NavItem>
      <NavItem
        name="rewards"
        :label="MODULE_LABELS.rewards"
        :expanded="expanded"
        :active="route.name === 'rewards'"
      >
        <IconAward />
      </NavItem>
      <NavItem
        name="awards"
        :label="MODULE_LABELS.awards"
        :expanded="expanded"
        :active="route.name === 'awards'"
      >
        <IconCake />
      </NavItem>
      <NavItem
        name="passports"
        :label="MODULE_LABELS.passports"
        :expanded="expanded"
        :active="route.name === 'passports'"
      >
        <IconPassport />
      </NavItem>
      <NavItem
        name="events"
        :label="MODULE_LABELS.events"
        :expanded="expanded"
        :active="route.name === 'events'"
      >
        <IconEmployees />
      </NavItem>
      <NavItem
        v-if="auth.isAdmin()"
        name="settings"
        :label="MODULE_LABELS.settings"
        :expanded="expanded"
        :active="route.name === 'settings'"
      >
        <IconSettings />
      </NavItem>
    </nav>

    <div class="btn-box">
      <button
        type="button"
        class="toggle-btn"
        :aria-expanded="expanded"
        aria-controls="sidebar-nav"
        :aria-label="expanded ? 'Свернуть меню' : 'Развернуть меню'"
        @click="$emit('toggle')"
      >
        {{ expanded ? '←' : '→' }}
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 100%;
  padding: 1rem 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  position: sticky;
  top: 1rem;
  height: calc(100vh - 2rem);
  min-height: 0;
}

.brand-div {
  display: flex;
  flex-direction: row;
  align-items: center;
  flex-shrink: 0;
}

.brand {
  width: 44px;
  height: 44px;
  margin-left: 10px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, #2f6fed, #6ea1ff);
  color: white;
  display: grid;
  place-items: center;
  font-weight: 700;
}

.brand-label {
  margin-left: 10px;
  font-size: 0.85rem;
  line-height: 1.25;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-gutter: stable;
}

.btn-box {
  flex-shrink: 0;
}

.toggle-btn {
  width: 100%;
  height: 44px;
  margin: 0 auto;
  border-radius: var(--radius-lg);
  border: none;
  background: #6ea1ff;
  color: white;
  display: grid;
  place-items: center;
  font-weight: 700;
  cursor: pointer;
  transition: background var(--transition), transform var(--transition),
    box-shadow var(--transition);
}

.toggle-btn:hover {
  background: #2f6fed;
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(47, 111, 237, 0.28);
}

.toggle-btn:active {
  transform: scale(0.94);
  box-shadow: none;
}

.brand {
  transition: transform var(--transition-slow) var(--ease-out);
}

.sidebar:hover .brand {
  transform: rotate(-6deg) scale(1.05);
}
</style>
