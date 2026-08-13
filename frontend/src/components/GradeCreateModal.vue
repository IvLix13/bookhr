<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import GradeCatalogForm from '@/components/GradeCatalogForm.vue'
import { useFocusTrap } from '@/composables/useFocusTrap'
import type { Grade } from '@/types'

const props = withDefaults(
  defineProps<{
    open: boolean
    initialName?: string
  }>(),
  {
    initialName: '',
  },
)

const emit = defineEmits<{
  close: []
  saved: [grade: Grade]
}>()

const modalRef = ref<HTMLElement | null>(null)
const { activate, deactivate } = useFocusTrap(modalRef, () => props.open)

function closeModal() {
  emit('close')
}

function onSaved(grade: Grade) {
  emit('saved', grade)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.open) {
    closeModal()
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      activate()
      window.addEventListener('keydown', onKeydown)
    } else {
      deactivate()
      window.removeEventListener('keydown', onKeydown)
    }
  },
)

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  deactivate()
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="overlay" @click.self="closeModal">
        <section
          ref="modalRef"
          class="modal card"
          role="dialog"
          aria-modal="true"
          aria-label="Добавить грейд"
          tabindex="-1"
        >
          <header class="modal-header">
            <h2>Новый грейд</h2>
            <button class="btn ghost" type="button" aria-label="Закрыть" @click="closeModal">
              ×
            </button>
          </header>
          <GradeCatalogForm
            mode="create"
            :initial-name="initialName"
            @saved="onSaved"
            @cancel="closeModal"
          />
        </section>
      </div>
    </Transition>
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
  z-index: 1000;
}

.modal {
  width: min(560px, 100%);
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

.modal-header h2 {
  margin: 0;
}
</style>
