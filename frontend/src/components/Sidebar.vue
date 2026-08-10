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
import { useAuthStore } from '@/stores/auth'
import { useRoute } from 'vue-router'

import { ref } from 'vue'

const isSidebarOpen = ref(false)

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value
}

const route = useRoute()
const auth = useAuthStore()
</script>

<template>
  <aside class="sidebar card" :class="{ 'sidebar-open': isSidebarOpen }">
    <div class="brand-div">
      <div class="brand">К</div>
      <label v-if="isSidebarOpen" class="label">Календарь событий</label>
    </div>

    <nav>
      <NavItem
        name="calendar"
        label="Календарь"
        :expanded="isSidebarOpen"
        :active="route.name === 'calendar'"
      >
        <IconCalendar />
      </NavItem>
      <NavItem
        name="statistics"
        label="Статистика"
        :expanded="isSidebarOpen"
        :active="route.name === 'statistics'"
      >
        <IconStats />
      </NavItem>
      <NavItem
        name="employees"
        label="Сотрудники"
        :expanded="isSidebarOpen"
        :active="route.name === 'employees'"
      >
        <IconTable />
      </NavItem>
      <NavItem name="import" label="Импорт" :expanded="isSidebarOpen" :active="route.name === 'import'">
        <IconImport />
      </NavItem>
      <NavItem
        name="event-create"
        label="Событие"
        :expanded="isSidebarOpen"
        :active="route.name === 'event-create'"
      >
        <IconEvent />
      </NavItem>
      <NavItem
        name="contracts"
        label="Договоры"
        :expanded="isSidebarOpen"
        :active="route.name === 'contracts'"
      >
        <IconContract />
      </NavItem>
      <NavItem name="grades" label="грейды" :expanded="isSidebarOpen" :active="route.name === 'grades'">
        <IconGrade />
      </NavItem>
      <NavItem
        name="rewards"
        label="Поощрения"
        :expanded="isSidebarOpen"
        :active="route.name === 'rewards'"
      >
        <IconAward />
      </NavItem>
      <NavItem
        name="awards"
        label="Поощрения за стаж"
        :expanded="isSidebarOpen"
        :active="route.name === 'awards'"
      >
        <IconCake />
      </NavItem>
      <NavItem
        name="passports"
        label="Паспорта"
        :expanded="isSidebarOpen"
        :active="route.name === 'passports'"
      >
        <IconPassport />
      </NavItem>
      <NavItem name="events" label="Мероприятия" :expanded="isSidebarOpen" :active="route.name === 'events'">
        <IconEmployees />
      </NavItem>
      <NavItem
        v-if="auth.isAdmin()"
        name="settings"
        label="Настройки"
        :expanded="isSidebarOpen"
        :active="route.name === 'settings'"
      >
        <IconSettings />
      </NavItem>
    </nav>
    <div class="btn-box">
      <button class="toggle-btn" @click="toggleSidebar">
        {{ isSidebarOpen ? '←' : '→' }}
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  padding: 1rem 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  position: sticky;
  top: 1rem;
  height: calc(100vh - 2rem);
}

.brand-div {
  display: flex;
  flex-direction: row;
  align-content: center;
}

.brand {
  width: 44px;
  height: 44px;
  margin-left: 10px;
  border-radius: 12px;
  background: linear-gradient(135deg, #2f6fed, #6ea1ff);
  color: white;
  display: grid;
  place-items: center;
  font-weight: 700;
}

nav {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  overflow-y: hidden;
}

.sidebar-open {
  width: 240px;
}

.label {
  margin-left: 10px;
  font-size: 14px;
  text-align: center;
  align-content: center;
}

.toggle-btn {
  width: 100%;
  height: 44px;
  margin: 0 auto;
  border-radius: 12px;
  border: none;
  background: #6ea1ff;
  color: white;
  display: grid;
  place-items: center;
  font-weight: 700;
  cursor: pointer;
}
.toggle-btn:hover {
  background: #2f6fed;
  transform: translateY(-1px);
}

.aside {
  justify-content: left;
  overflow: hidden;
}
</style>
