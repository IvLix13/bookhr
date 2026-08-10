import { onUnmounted, type Ref } from 'vue'

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function useFocusTrap(containerRef: Ref<HTMLElement | null>, active: () => boolean) {
  let previousFocus: HTMLElement | null = null

  function getFocusable(container: HTMLElement): HTMLElement[] {
    return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
      (el) => !el.hasAttribute('disabled') && el.offsetParent !== null,
    )
  }

  function onKeydown(event: KeyboardEvent) {
    if (!active() || event.key !== 'Tab') return
    const container = containerRef.value
    if (!container) return

    const focusable = getFocusable(container)
    if (!focusable.length) return

    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    const current = document.activeElement as HTMLElement | null

    if (event.shiftKey && current === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && current === last) {
      event.preventDefault()
      first.focus()
    }
  }

  function activate() {
    previousFocus = document.activeElement as HTMLElement | null
    window.setTimeout(() => {
      const container = containerRef.value
      if (!container) return
      const focusable = getFocusable(container)
      ;(focusable[0] ?? container).focus()
    }, 0)
    document.addEventListener('keydown', onKeydown)
  }

  function deactivate() {
    document.removeEventListener('keydown', onKeydown)
    previousFocus?.focus()
    previousFocus = null
  }

  onUnmounted(deactivate)

  return { activate, deactivate }
}
