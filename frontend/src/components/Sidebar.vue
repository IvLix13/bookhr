<script setup lang="ts">
import NavItem from '@/components/NavItem.vue'
import {
  isSidebarNavItemActive,
  isSidebarNavItemVisible,
  resolveSidebarNavName,
  sidebarNavItems,
  sidebarToggleBackground,
} from '@/config/sidebarNav'
import { MODULE_LABELS } from '@/utils/labels'
import { useAuthStore } from '@/stores/auth'
import { computed } from 'vue'
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

const visibleNavItems = computed(() =>
  sidebarNavItems.filter((item) => isSidebarNavItemVisible(item, auth)),
)

const toggleStyle = computed(() =>
  sidebarToggleBackground ? { '--toggle-btn-bg': `url(${sidebarToggleBackground})` } : undefined,
)
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
        v-for="item in visibleNavItems"
        :key="resolveSidebarNavName(item, auth)"
        :name="resolveSidebarNavName(item, auth)"
        :label="MODULE_LABELS[item.labelKey]"
        :expanded="expanded"
        :active="isSidebarNavItemActive(item, route)"
        :background="item.background"
        :background-active="item.backgroundActive"
      >
        <component :is="item.icon" />
      </NavItem>
    </nav>

    <div class="btn-box">
      <button
        type="button"
        class="toggle-btn"
        :class="{ 'has-bg': expanded }"
        :style="expanded ? toggleStyle : undefined"
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
  transition: transform var(--transition-slow) var(--ease-out);
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
  transition:
    background var(--transition),
    transform var(--transition),
    box-shadow var(--transition),
    filter var(--transition);
}

.toggle-btn.has-bg {
  background-color: transparent;
  background-image: var(--toggle-btn-bg);
  background-repeat: no-repeat;
  background-position: center;
  background-size: 100% 100%;
}

.toggle-btn:hover {
  background-color: #2f6fed;
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(47, 111, 237, 0.28);
}

.toggle-btn.has-bg:hover {
  background-color: transparent;
  filter: brightness(1.03);
}

.toggle-btn:active {
  transform: scale(0.94);
  box-shadow: none;
}

.sidebar:hover .brand {
  transform: rotate(-6deg) scale(1.05);
}
</style>
