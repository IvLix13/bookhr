<script setup lang="ts">
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()
</script>

<template>
  <TransitionGroup
    tag="div"
    name="toast"
    class="toast-viewport"
    aria-live="polite"
    aria-relevant="additions"
  >
    <article
      v-for="item in toast.items"
      :key="item.id"
      class="toast"
      :class="item.variant"
      role="status"
    >
      <span>{{ item.message }}</span>
      <button type="button" class="toast-close" aria-label="Закрыть" @click="toast.dismiss(item.id)">
        ×
      </button>
    </article>
  </TransitionGroup>
</template>

<style scoped>
.toast-viewport {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 2000;
  display: grid;
  gap: 0.5rem;
  width: min(360px, calc(100vw - 2rem));
}

.toast {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--surface);
  box-shadow: var(--shadow);
}

.toast.success {
  border-color: #b8e6cc;
}

.toast.error {
  border-color: #f5c2c2;
}

.toast.warning {
  border-color: #f3d59a;
}

.toast.info {
  border-color: var(--accent-soft);
}

.toast-close {
  border: none;
  background: transparent;
  color: var(--muted);
  font-size: 1.1rem;
  line-height: 1;
}
</style>
