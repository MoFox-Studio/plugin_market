import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api'
import type { AuthStatus, Author } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const viewer = ref<Author | null>(null)
  const loading = ref(false)

  const isAuthenticated = computed(() => !!viewer.value)
  const isAdmin = computed(() => viewer.value?.is_admin === true)

  async function loadViewer(force = false): Promise<void> {
    if (!force && viewer.value !== null) return
    loading.value = true
    try {
      const auth = await api.get<AuthStatus>('/api/v1/me')
      viewer.value = auth?.authenticated ? (auth.user ?? null) : null
    } catch {
      viewer.value = null
    } finally {
      loading.value = false
    }
  }

  async function logout(): Promise<void> {
    await api.post('/api/v1/auth/logout').catch(() => {})
    viewer.value = null
  }

  function getLoginUrl(redirectTo?: string): string {
    const rd = encodeURIComponent(redirectTo || location.pathname + location.search)
    return `/api/v1/auth/github/login?redirect_to=${rd}`
  }

  return { viewer, loading, isAuthenticated, isAdmin, loadViewer, logout, getLoginUrl }
})
