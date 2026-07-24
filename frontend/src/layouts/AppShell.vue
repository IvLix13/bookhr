<script setup lang="ts">
import Sidebar from '@/components/Sidebar.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <div class="shell">
    <Sidebar />
    <main>
      <header class="topbar">
        <div>
          <h1>Bookuchet</h1>
          <p>Оперативный учёт кадровых событий</p>
        </div>
        <div class="user-block">
          <span>{{ auth.user?.full_name }}</span>
          <button class="btn ghost" @click="auth.logout()">Выйти</button>
        </div>
      </header>
      <RouterView v-slot="{ Component }">
        <Transition name="fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: var(--sidebar-width) 1fr;
  gap: 1rem;
  padding: 1rem;
}

main {
  min-width: 0;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.topbar h1 {
  margin: 0;
  font-size: 1.5rem;
}

.topbar p {
  margin: 0.2rem 0 0;
  color: var(--muted);
}

.user-block {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
</style>
