import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, setCsrfToken } from '@/api/client'
import type { User } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const loading = ref(false)

  async function fetchMe() {
    loading.value = true
    try {
      user.value = (await api.me()) as User
    } catch {
      user.value = null
      setCsrfToken(null)
    } finally {
      loading.value = false
    }
  }

  async function ensureCsrf() {
    try {
      await api.fetchCsrf()
    } catch {
      // login flow will rotate token after successful auth
    }
  }

  async function login(username: string, password: string) {
    user.value = (await api.login(username, password)) as User
  }

  async function logout() {
    try {
      await api.logout()
    } catch {
      // Session may already be gone; clear client state anyway.
    } finally {
      user.value = null
      setCsrfToken(null)
    }
  }

  function clearSession() {
    user.value = null
    setCsrfToken(null)
  }

  const canEdit = () => user.value?.role === 'admin' || user.value?.role === 'hr'
  const isAdmin = () => user.value?.role === 'admin'
  const canManageNotifications = () => canEdit()

  return {
    user,
    loading,
    fetchMe,
    ensureCsrf,
    login,
    logout,
    clearSession,
    canEdit,
    isAdmin,
    canManageNotifications,
  }
})
