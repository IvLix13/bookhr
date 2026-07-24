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
  IconTable,
} from '@/components/icons'
import { useAuthStore } from '@/stores/auth'
import { useRoute } from 'vue-router'

const route = useRoute()
const auth = useAuthStore()
</script>

<template>
  <aside class="sidebar card">
    <div class="brand">B</div>
    <nav>
      <NavItem name="calendar" label="Календарь" :active="route.name === 'calendar'">
        <IconCalendar />
      </NavItem>
      <NavItem name="employees" label="Сотрудники" :active="route.name === 'employees'">
        <IconTable />
      </NavItem>
      <NavItem name="import" label="Импорт" :active="route.name === 'import'">
        <IconImport />
      </NavItem>
      <NavItem name="event-create" label="Событие" :active="route.name === 'event-create'">
        <IconEvent />
      </NavItem>
      <NavItem name="contracts" label="Контракты" :active="route.name === 'contracts'">
        <IconContract />
      </NavItem>
      <NavItem name="grades" label="Грейды" :active="route.name === 'grades'">
        <IconGrade />
      </NavItem>
      <NavItem name="awards" label="Поощрения" :active="route.name === 'awards'">
        <IconAward />
      </NavItem>
      <NavItem name="passports" label="Паспорта" :active="route.name === 'passports'">
        <IconPassport />
      </NavItem>
      <NavItem name="events" label="Мероприятия" :active="route.name === 'events'">
        <IconEmployees />
      </NavItem>
      <NavItem name="grade-catalog" label="Справочник" :active="route.name === 'grade-catalog'">
        <IconGrade />
      </NavItem>
      <NavItem v-if="auth.isAdmin()" name="settings" label="Настройки" :active="route.name === 'settings'">
        <IconSettings />
      </NavItem>
    </nav>
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

.brand {
  width: 44px;
  height: 44px;
  margin: 0 auto;
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
  overflow-y: auto;
}
</style>
