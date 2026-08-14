<script setup lang="ts">
const props = defineProps<{
  open: boolean
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
}>()

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="overlay" @click.self="emit('cancel')">
      <section
        class="card modal confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        :aria-labelledby="`confirm-title-${title}`"
      >
        <header class="modal-header">
          <h3 :id="`confirm-title-${title}`">{{ title }}</h3>
        </header>
        <p class="confirm-message">{{ message }}</p>
        <footer class="modal-actions">
          <button class="btn secondary" type="button" @click="emit('cancel')">
            {{ cancelLabel ?? 'Отмена' }}
          </button>
          <button
            class="btn"
            :class="danger ? 'danger' : 'primary'"
            type="button"
            @click="emit('confirm')"
          >
            {{ confirmLabel ?? 'Подтвердить' }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: grid;
  place-items: center;
  padding: 1rem;
  z-index: 1100;
}

.confirm-dialog {
  width: min(28rem, 92vw);
  max-height: calc(100vh - 2rem);
  overflow: auto;
  padding: 1rem;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: start;
  margin-bottom: 0.75rem;
}

.modal-header h3 {
  margin: 0;
}

.confirm-message {
  margin: 0 0 1rem;
  color: var(--muted);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.btn.danger {
  background: var(--danger);
  color: #fff;
}
</style>
