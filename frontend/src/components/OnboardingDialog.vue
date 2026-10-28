<script setup lang="ts">
import { onMounted, ref, useId } from 'vue'
import { useFocusTrap } from '@/composables/useFocusTrap'
import { useBodyScrollLock } from '@/composables/useBodyScrollLock'
defineProps<{ title: string; busy?: boolean; layout?: 'plan'; consumeEscape?: () => boolean }>()
const emit = defineEmits<{ close: [] }>()
const modal = ref<HTMLElement | null>(null)
const id = useId()
const focus = useFocusTrap(modal, () => true)
useBodyScrollLock()
onMounted(focus.activate)
</script>

<template>
  <Teleport to="body">
    <div class="dialog-overlay" @keydown.esc.stop.prevent="!consumeEscape?.() && !busy && emit('close')">
      <section ref="modal" class="card onboarding-dialog" :class="{ 'plan-layout': layout === 'plan' }" role="dialog" aria-modal="true" :aria-labelledby="id" tabindex="-1">
        <header><h2 :id="id">{{ title }}</h2><div class="header-actions"><slot name="header-actions" /><button class="btn secondary" :disabled="busy" aria-label="Закрыть окно" @click="emit('close')">×</button></div></header>
        <slot />
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-overlay { position: fixed; inset: 0; z-index: 1100; background: #0f172a80; display: grid; place-items: center; padding: 1rem; }
.onboarding-dialog { width: min(1000px, 100%); max-height: calc(100dvh - 2rem); overflow: auto; padding: 1rem; min-width: 0; }
header { display: flex; justify-content: space-between; align-items: start; gap: 1rem; margin-bottom: 1rem; }
h2 { margin: 0; overflow-wrap: anywhere; }
.header-actions { display: flex; gap: .5rem; flex-shrink: 0; }
.plan-layout { width: min(1500px, 100%); height: min(900px, calc(100dvh - 2rem)); display: flex; flex-direction: column; overflow: hidden; }
.plan-layout > header { flex-shrink: 0; position: relative; z-index: 5; }
@media (max-width: 640px), (max-height: 650px) { .plan-layout { height: auto; overflow: auto; } }
</style>
