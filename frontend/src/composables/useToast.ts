import { useToastStore } from '@/stores/toast'

export function useToast() {
  const store = useToastStore()
  return {
    success: store.success,
    error: store.error,
    warning: store.warning,
    info: store.info,
    dismiss: store.dismiss,
  }
}
