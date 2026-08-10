import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

const STORAGE_KEY = 'bookuchet:sidebar-expanded'

function readExpanded(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export const useUiStore = defineStore('ui', () => {
  const sidebarExpanded = ref(readExpanded())

  watch(sidebarExpanded, (value) => {
    try {
      localStorage.setItem(STORAGE_KEY, value ? '1' : '0')
    } catch {
      // ignore storage errors
    }
  })

  function toggleSidebar() {
    sidebarExpanded.value = !sidebarExpanded.value
  }

  return { sidebarExpanded, toggleSidebar }
})
