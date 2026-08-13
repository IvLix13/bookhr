<script setup lang="ts">
defineProps<{
  loading?: boolean
  refreshing?: boolean
  error?: string
  empty?: boolean
  emptyText?: string
  hasData?: boolean
}>()

defineEmits<{
  retry: []
}>()
</script>

<template>
  <div class="page-state" :aria-busy="loading || refreshing ? 'true' : undefined">
    <Transition name="fade" mode="out-in">
      <div v-if="loading" key="loading" class="state-message loading">
        <span class="spinner" aria-hidden="true"></span>
        <span>Загрузка...</span>
      </div>
      <div v-else-if="error && !hasData" key="error" class="state-message error">
        <p>{{ error }}</p>
        <button class="btn secondary" type="button" @click="$emit('retry')">Повторить</button>
      </div>
      <div v-else-if="empty && !hasData" key="empty" class="state-message">
        {{ emptyText ?? 'Нет данных' }}
      </div>
      <div v-else key="content">
        <div v-if="error" class="state-message error inline-error">
          <p>{{ error }}</p>
          <button class="btn secondary" type="button" @click="$emit('retry')">Повторить</button>
        </div>
        <slot />
      </div>
    </Transition>
    <Transition name="fade">
      <div v-if="refreshing" class="refresh-indicator" aria-live="polite">
        <span class="spinner spinner-sm" aria-hidden="true"></span>
        <span>Обновление...</span>
      </div>
    </Transition>
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

.state-message.loading {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.refresh-indicator {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.spinner-sm {
  width: 0.9rem;
  height: 0.9rem;
  border-width: 2px;
}

.state-message.error {
  color: var(--danger);
  display: grid;
  gap: 0.75rem;
  justify-items: start;
}

.state-message.error.inline-error {
  margin-bottom: 0.75rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid color-mix(in srgb, var(--danger) 35%, transparent);
  border-radius: 0.5rem;
  background: color-mix(in srgb, var(--danger) 8%, transparent);
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
