<script setup lang="ts">
import GlobalSearch from '@/components/GlobalSearch.vue'
import Sidebar from '@/components/Sidebar.vue'
import ToastViewport from '@/components/ToastViewport.vue'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { storeToRefs } from 'pinia'

const auth = useAuthStore()
const ui = useUiStore()
const { sidebarExpanded } = storeToRefs(ui)
</script>

<template>
  <div class="shell" :class="{ 'sidebar-expanded': sidebarExpanded }">
    <a class="skip-link" href="#main-content">Перейти к содержимому</a>
    <Sidebar :expanded="sidebarExpanded" @toggle="ui.toggleSidebar()" />
    <main id="main-content">
      <header class="topbar">
        <div>
          <h1>Учет кадровых событий</h1>
        </div>
        <div class="topbar-actions">
          <GlobalSearch />
          <div class="user-block">
            <span>{{ auth.user?.full_name }}</span>
            <button class="btn ghost" type="button" @click="auth.logout()">Выйти</button>
          </div>
        </div>
      </header>
      <RouterView v-slot="{ Component }">
        <Transition name="fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>
    <ToastViewport />
  </div>
</template>

<style scoped>
.shell {
  --sidebar-width: 84px;
  min-height: 100vh;
  display: grid;
  grid-template-columns: var(--sidebar-width) 1fr;
  gap: 1rem;
  padding: 1rem;
  transition: grid-template-columns var(--transition);
}

.shell.sidebar-expanded {
  --sidebar-width: 240px;
}

main {
  min-width: 0;
}

.skip-link {
  position: absolute;
  left: -9999px;
  top: 0;
  background: var(--surface);
  color: var(--text);
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius-sm);
  z-index: 3000;
}

.skip-link:focus {
  left: 1rem;
  top: 1rem;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.topbar h1 {
  margin: 0;
  font-size: 1.5rem;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.user-block {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
</style>
