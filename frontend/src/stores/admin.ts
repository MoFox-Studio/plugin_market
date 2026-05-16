import { ref } from 'vue'
import { defineStore } from 'pinia'
import api from '@/api'
import type { BulkAction, BulkActionItemResult, BulkActionResult } from '@/types'

interface AdminFilters {
  query: string
  status: string
  trustLevel: string
  owner: string
  category: string
  tag: string
  pendingOnly: boolean
  action: string
}

interface AdminPagination {
  page: number
  pageSize: number
  total: number
}

export const useAdminStore = defineStore('admin', () => {
  const selectedIds = ref<string[]>([])
  const filters = ref<AdminFilters>({
    query: '',
    status: '',
    trustLevel: '',
    owner: '',
    category: '',
    tag: '',
    pendingOnly: false,
    action: '',
  })
  const pagination = ref<AdminPagination>({
    page: 1,
    pageSize: 20,
    total: 0,
  })
  const bulkPending = ref(false)
  const bulkAction = ref<BulkAction | null>(null)
  const bulkReason = ref('')
  const bulkResults = ref<BulkActionItemResult[]>([])

  function toggleSelection(pluginId: string): void {
    if (selectedIds.value.includes(pluginId)) {
      selectedIds.value = selectedIds.value.filter((item) => item !== pluginId)
      return
    }
    selectedIds.value = [...selectedIds.value, pluginId]
  }

  function setSelection(pluginIds: string[]): void {
    selectedIds.value = Array.from(new Set(pluginIds.filter(Boolean)))
  }

  function clearSelection(): void {
    selectedIds.value = []
  }

  function setFilter<K extends keyof AdminFilters>(key: K, value: AdminFilters[K]): void {
    filters.value = {
      ...filters.value,
      [key]: value,
    }
  }

  function resetFilters(): void {
    filters.value = {
      query: '',
      status: '',
      trustLevel: '',
      owner: '',
      category: '',
      tag: '',
      pendingOnly: false,
      action: '',
    }
  }

  function setPagination(partial: Partial<AdminPagination>): void {
    pagination.value = {
      ...pagination.value,
      ...partial,
    }
  }

  async function applyBulk(action: BulkAction, params?: Record<string, unknown>): Promise<BulkActionResult> {
    bulkPending.value = true
    bulkAction.value = action
    try {
      const result = await api.admin.bulkApply({
        plugin_ids: selectedIds.value,
        action,
        params: params || {},
      })
      bulkResults.value = result.results || []
      return result
    } finally {
      bulkPending.value = false
    }
  }

  function clearBulkState(): void {
    bulkAction.value = null
    bulkReason.value = ''
    bulkResults.value = []
  }

  return {
    selectedIds,
    filters,
    pagination,
    bulkPending,
    bulkAction,
    bulkReason,
    bulkResults,
    toggleSelection,
    setSelection,
    clearSelection,
    setFilter,
    resetFilters,
    setPagination,
    applyBulk,
    clearBulkState,
  }
})