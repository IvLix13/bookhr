import { ref } from 'vue'
import { defineStore } from 'pinia'

export type ToastVariant = 'success' | 'error' | 'warning' | 'info'

export interface ToastItem {
  id: number
  message: string
  variant: ToastVariant
  durationMs: number
}

let nextId = 1

export const useToastStore = defineStore('toast', () => {
  const items = ref<ToastItem[]>([])

  function dismiss(id: number) {
    items.value = items.value.filter((item) => item.id !== id)
  }

  function push(message: string, variant: ToastVariant = 'info', durationMs = 4000) {
    const trimmed = message.trim()
    if (!trimmed) return

    const duplicate = items.value.find((item) => item.message === trimmed && item.variant === variant)
    if (duplicate) return

    const id = nextId++
    items.value = [...items.value, { id, message: trimmed, variant, durationMs }]

    if (durationMs > 0) {
      window.setTimeout(() => dismiss(id), durationMs)
    }
  }

  function success(message: string) {
    push(message, 'success')
  }

  function error(message: string) {
    push(message, 'error', 6000)
  }

  function warning(message: string) {
    push(message, 'warning', 5000)
  }

  function info(message: string) {
    push(message, 'info')
  }

  return { items, push, dismiss, success, error, warning, info }
})
