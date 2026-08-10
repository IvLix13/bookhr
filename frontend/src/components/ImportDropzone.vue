<script setup lang="ts">
import { ref } from 'vue'

const props = withDefaults(
  defineProps<{
    accept?: string
    disabled?: boolean
    label?: string
    hint?: string
  }>(),
  {
    accept: '.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    disabled: false,
    label: 'Перетащите Excel-файл сюда',
    hint: 'или нажмите, чтобы выбрать файл (.xlsx)',
  },
)

const emit = defineEmits<{
  select: [file: File]
}>()

const dragActive = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)

function isAccepted(file: File): boolean {
  const extension = file.name.toLowerCase().endsWith('.xlsx')
  const mime = file.type.includes('spreadsheet') || file.type === ''
  return extension || mime
}

function emitFile(file: File | null | undefined) {
  if (!file || props.disabled || !isAccepted(file)) return
  emit('select', file)
}

function onInputChange(event: Event) {
  const input = event.target as HTMLInputElement
  emitFile(input.files?.[0])
  input.value = ''
}

function onDrop(event: DragEvent) {
  event.preventDefault()
  dragActive.value = false
  if (props.disabled) return
  emitFile(event.dataTransfer?.files?.[0])
}

function onDragOver(event: DragEvent) {
  event.preventDefault()
  if (!props.disabled) dragActive.value = true
}

function onDragLeave() {
  dragActive.value = false
}

function openPicker() {
  if (!props.disabled) inputRef.value?.click()
}
</script>

<template>
  <div
    class="import-dropzone"
    :class="{ active: dragActive, disabled }"
    role="button"
    tabindex="0"
    :aria-disabled="disabled ? 'true' : undefined"
    @click="openPicker"
    @keydown.enter.prevent="openPicker"
    @keydown.space.prevent="openPicker"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <input
      ref="inputRef"
      type="file"
      class="sr-only"
      :accept="accept"
      :disabled="disabled"
      @change="onInputChange"
    />
    <strong>{{ label }}</strong>
    <p>{{ hint }}</p>
  </div>
</template>

<style scoped>
.import-dropzone {
  border: 2px dashed var(--border);
  border-radius: var(--radius);
  padding: 2rem 1.25rem;
  text-align: center;
  background: var(--bg);
  cursor: pointer;
  transition: border-color var(--transition), background var(--transition);
}

.import-dropzone:hover,
.import-dropzone.active {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.import-dropzone.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.import-dropzone strong {
  display: block;
  margin-bottom: 0.35rem;
}

.import-dropzone p {
  margin: 0;
  color: var(--muted);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
