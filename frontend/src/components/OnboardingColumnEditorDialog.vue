<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useFocusTrap } from '@/composables/useFocusTrap'
import { useBodyScrollLock } from '@/composables/useBodyScrollLock'
defineProps<{ busy: boolean }>()
const emit = defineEmits<{ close: [] }>()
const modal = ref<HTMLElement | null>(null)
const focus = useFocusTrap(modal, () => true)
useBodyScrollLock()
onMounted(focus.activate)
</script>
<template><Teleport to="body"><div class="editor-overlay" @keydown.esc.stop.prevent="!busy && emit('close')"><section ref="modal" class="card editor-dialog" role="dialog" aria-modal="true" aria-label="Редактор этапа" tabindex="-1"><slot /></section></div></Teleport></template>
<style scoped>
.editor-overlay { position:fixed;inset:0;z-index:1300;background:#0f172a80;display:grid;place-items:center;padding:1rem; }
.editor-dialog { width:min(660px,100%);max-height:calc(100dvh - 2rem);overflow:auto;padding:1.5rem; }
</style>
