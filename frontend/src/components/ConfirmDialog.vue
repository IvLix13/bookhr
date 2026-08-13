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
.confirm-dialog {
  width: min(28rem, 92vw);
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
