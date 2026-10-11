import { onUnmounted, type Ref } from 'vue'

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

const traps: Array<{ previousFocus: HTMLElement | null }> = []

export function useFocusTrap(containerRef: Ref<HTMLElement | null>, active: () => boolean) {
  const token = { previousFocus: null as HTMLElement | null }
  let activatedContainer: HTMLElement | null = null

  function getFocusable(container: HTMLElement): HTMLElement[] {
    return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
      (el) => !el.hasAttribute('disabled') && el.offsetParent !== null,
    )
  }

  function onKeydown(event: KeyboardEvent) {
    if (traps.at(-1) !== token || !active() || event.key !== 'Tab') return
    const container = containerRef.value
    if (!container) return

    const focusable = getFocusable(container)
    if (!focusable.length) { event.preventDefault(); container.focus(); return }

    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    const current = document.activeElement as HTMLElement | null

    if (event.shiftKey && (current === first || !container.contains(current))) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && (current === last || !container.contains(current))) {
      event.preventDefault()
      first.focus()
    }
  }

  function activate() {
    if (traps.includes(token)) return
    traps.push(token)
    activatedContainer = containerRef.value
    token.previousFocus = document.activeElement as HTMLElement | null
    window.setTimeout(() => {
      const container = containerRef.value
      if (!container || traps.at(-1) !== token) return
      const focusable = getFocusable(container)
      ;(focusable[0] ?? container).focus()
    }, 0)
    document.addEventListener('keydown', onKeydown)
  }

  function deactivate() {
    document.removeEventListener('keydown', onKeydown)
    const index = traps.indexOf(token)
    const wasTop = index === traps.length - 1
    const next = traps[index + 1]
    if (index >= 0 && next && next.previousFocus && activatedContainer?.contains(next.previousFocus)) {
      // A parent dialog may unmount before its child. Pass its opener along
      // so the final dialog restores focus outside the removed subtree.
      next.previousFocus = token.previousFocus
    }
    if (index >= 0) traps.splice(index, 1)
    if (index >= 0 && wasTop && token.previousFocus?.isConnected) token.previousFocus.focus()
    token.previousFocus = null
    activatedContainer = null
  }

  onUnmounted(deactivate)

  return { activate, deactivate }
}
