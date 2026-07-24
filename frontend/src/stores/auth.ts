import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'
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
    } finally {
      loading.value = false
    }
  }

  async function login(username: string, password: string) {
    user.value = (await api.login(username, password)) as User
  }

  async function logout() {
    await api.logout()
    user.value = null
  }

  const canEdit = () => user.value?.role === 'admin' || user.value?.role === 'hr'
  const isAdmin = () => user.value?.role === 'admin'

  return { user, loading, fetchMe, login, logout, canEdit, isAdmin }
})
