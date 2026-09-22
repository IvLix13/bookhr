<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import OnboardingColumns from '@/components/OnboardingColumns.vue'
import { useFocusTrap } from '@/composables/useFocusTrap'
import type { OnboardingColumn } from '@/types/onboarding'

const props = defineProps<{ columns: OnboardingColumn[]; refreshing?: boolean; refreshError?: string }>()
const emit = defineEmits<{ close: []; changed: [] }>()
const modal = ref<HTMLElement | null>(null)
const editorState = ref({ dirty: false, busy: false })
const keepEditing = ref<HTMLButtonElement | null>(null)
const closeButton = ref<HTMLButtonElement | null>(null)
const confirming = ref(false)
const busy = computed(() => !!props.refreshing || editorState.value.busy)
const focus = useFocusTrap(modal, () => true)
let previousOverflow = ''
onMounted(() => {
  previousOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  focus.activate()
})
onUnmounted(() => { document.body.style.overflow = previousOverflow })
async function requestClose() {
  if (busy.value) return
  if (editorState.value.dirty) {
    confirming.value = true
    await nextTick()
    keepEditing.value?.focus()
  } else emit('close')
}
async function cancelClose() {
  confirming.value = false
  await nextTick()
  closeButton.value?.focus()
}
</script>

<template>
  <Teleport to="body">
    <div class="columns-overlay" @keydown.esc.stop.prevent="confirming ? cancelClose() : requestClose()">
      <section ref="modal" class="card columns-modal" role="dialog" aria-modal="true" aria-labelledby="columns-title" tabindex="-1">
        <header><h2 id="columns-title">Настройка этапов и полей</h2><button ref="closeButton" class="btn secondary" aria-label="Закрыть настройку этапов" :disabled="busy" @click="requestClose">×</button></header>
        <div key="editor-content" v-show="!confirming">
          <p v-if="refreshError" role="alert" class="error">{{ refreshError }} <button class="btn secondary" :disabled="busy" @click="emit('changed')">Повторить загрузку</button></p>
          <OnboardingColumns :columns="columns" @state="editorState = $event" @changed="emit('changed')" />
          <footer><button class="btn secondary" :disabled="busy" @click="requestClose">Закрыть</button></footer>
        </div>
        <div v-if="confirming" role="alert" class="close-confirm">
          <p>В форме есть несохранённые изменения. Закрыть окно и сбросить их?</p>
          <button ref="keepEditing" class="btn" @click="cancelClose">Продолжить редактирование</button>
          <button class="btn secondary" @click="emit('close')">Закрыть без сохранения</button>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.columns-overlay { position: fixed; inset: 0; z-index: 1100; background: #0f172a80; display: grid; place-items: center; padding: 1rem; }
.columns-modal { width: min(960px, 100%); max-height: calc(100dvh - 2rem); overflow: auto; padding: 1rem; }
header { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
h2 { margin: 0; }
footer { display: flex; justify-content: flex-end; }
.close-confirm { padding: 1rem 0; }
.close-confirm button { margin: .25rem; }
.error { color: var(--danger); }
</style>
