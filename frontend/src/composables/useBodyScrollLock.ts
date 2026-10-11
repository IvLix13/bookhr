import { onMounted, onUnmounted } from 'vue'

let locks = 0
let previousOverflow = ''
export function useBodyScrollLock() {
  onMounted(() => {
    if (!locks++) {
      previousOverflow = document.body.style.overflow
      document.body.style.overflow = 'hidden'
    }
  })
  onUnmounted(() => {
    if (!--locks) document.body.style.overflow = previousOverflow
  })
}
