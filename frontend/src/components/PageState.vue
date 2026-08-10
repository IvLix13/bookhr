<script setup lang="ts">
defineProps<{
  loading?: boolean
  refreshing?: boolean
  error?: string
  empty?: boolean
  emptyText?: string
}>()

defineEmits<{
  retry: []
}>()
</script>

<template>
  <div class="page-state" :aria-busy="loading || refreshing ? 'true' : undefined">
    <div v-if="loading" class="state-message">Загрузка...</div>
    <div v-else-if="error" class="state-message error">
      <p>{{ error }}</p>
      <button class="btn secondary" type="button" @click="$emit('retry')">Повторить</button>
    </div>
    <div v-else-if="empty" class="state-message">{{ emptyText ?? 'Нет данных' }}</div>
    <slot v-else />
    <div v-if="refreshing" class="refresh-indicator" aria-live="polite">Обновление...</div>
  </div>
</template>

<style scoped>
.page-state {
  position: relative;
}

.state-message {
  color: var(--muted);
  padding: 0.75rem 0;
}

.state-message.error {
  color: var(--danger);
  display: grid;
  gap: 0.75rem;
  justify-items: start;
}

.state-message.error p {
  margin: 0;
}

.refresh-indicator {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  font-size: 0.85rem;
  color: var(--muted);
}
</style>
