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
import { useAuthStore } from '@/stores/auth'
import { useRoute } from 'vue-router'

import { ref } from 'vue';

const isSidebarOpen = ref(false);

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value;
};

const route = useRoute()
const auth = useAuthStore()
</script>

<template>
  <aside class="sidebar card" :class="{'sidebar-open':isSidebarOpen}">
    <div class="brand-div">
      <div class="brand">B</div>
      <label class="label" v-if="isSidebarOpen">Василий Васильев</label>
    </div>
    
    <nav>
      <NavItem name="calendar" label="" :active="route.name === 'calendar'">
        <IconCalendar />
        <label class="label" v-if="isSidebarOpen">Календарь</label>
      </NavItem>
      <NavItem name="statistics" label="" :active="route.name === 'statistics'">
        <IconStats />
        <label class="label" v-if="isSidebarOpen">Статистика</label>
      </NavItem>
      <NavItem name="employees" label="" :active="route.name === 'employees'">
        <IconTable />
        <label class="label" v-if="isSidebarOpen">Сотрудники</label>
      </NavItem>
      <NavItem name="import" label="" :active="route.name === 'import'">
        <IconImport />
        <label class="label" v-if="isSidebarOpen">Импорт</label>
      </NavItem>
      <NavItem name="event-create" label="" :active="route.name === 'event-create'">
        <IconEvent />
        <label class="label" v-if="isSidebarOpen">Событие</label>
      </NavItem>
      <NavItem name="contracts" label="" :active="route.name === 'contracts'">
        <IconContract />
        <label class="label" v-if="isSidebarOpen">Контракты</label>
      </NavItem>
      <NavItem name="grades" label="" :active="route.name === 'grades'">
        <IconGrade />
        <label class="label" v-if="isSidebarOpen">Грейды</label>
      </NavItem>
      <NavItem name="awards" label="" :active="route.name === 'awards'">
        <IconAward />
        <label class="label" v-if="isSidebarOpen">Поощрения</label>
      </NavItem>
      <NavItem name="passports" label="" :active="route.name === 'passports'">
        <IconPassport />
        <label class="label" v-if="isSidebarOpen">Паспорта</label>
      </NavItem>
      <NavItem name="events" label="" :active="route.name === 'events'">
        <IconEmployees />
        <label class="label" v-if="isSidebarOpen">Мероприятия</label>
      </NavItem>
      <NavItem name="grade-catalog" label="" :active="route.name === 'grade-catalog'">
        <IconGrade />
        <label class="label" v-if="isSidebarOpen">Справочник</label>
      </NavItem>
      <NavItem v-if="auth.isAdmin()" name="settings" label="" :active="route.name === 'settings'">
        <IconSettings />
        <label class="label" v-if="isSidebarOpen">Настройки</label>
      </NavItem>
    </nav>
    <div class="btn-box">
      <button @click="toggleSidebar" class="toggle-btn">
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

.brand-div{
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

.nav-item{
  padding-left: 21px;
  flex-direction: row;
  justify-content: flex-start;
  align-items: center;
  gap: 0;
}

.nav-item :deep(.icon) {
  width: 22px;
  height: 22px;
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
.toggle-btn:hover{
  background: #2f6fed;
  transform: translateY(-1px);
}

.aside {
  justify-content: left;
  overflow: hidden;
}
</style>
