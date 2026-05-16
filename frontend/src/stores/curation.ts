import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { CurationEntry, CurationEntryCreate, CurationEntryUpdate } from '@/types'

type CurationDraft = CurationEntryCreate | CurationEntryUpdate

export const useCurationStore = defineStore('curation', () => {
  const items = ref<CurationEntry[]>([])
  const editingId = ref<number | null>(null)
  const draft = ref<CurationDraft | null>(null)
  const dirtyOrder = ref<number[]>([])

  function setItems(next: CurationEntry[]): void {
    items.value = next
  }

  function startCreate(defaults?: Partial<CurationEntryCreate>): void {
    editingId.value = null
    draft.value = {
      slot_type: 'featured_plugin',
      target_type: 'plugin',
      target_id: '',
      signature_plugin_id: null,
      sort_order: items.value.length,
      enabled: true,
      audience: 'all',
      display_meta: {},
      ...defaults,
    }
  }

  function startEdit(entry: CurationEntry): void {
    editingId.value = entry.id
    draft.value = {
      slot_type: entry.slot_type,
      target_type: entry.target_type,
      target_id: entry.target_id,
      signature_plugin_id: entry.signature_plugin_id || null,
      sort_order: entry.sort_order,
      enabled: entry.enabled,
      starts_at: entry.starts_at || null,
      ends_at: entry.ends_at || null,
      audience: entry.audience,
      display_meta: { ...entry.display_meta },
    }
  }

  function updateDraft(partial: Partial<CurationDraft>): void {
    draft.value = {
      ...(draft.value || {}),
      ...partial,
    }
  }

  function cancelEdit(): void {
    editingId.value = null
    draft.value = null
  }

  function setPendingOrder(ids: number[]): void {
    dirtyOrder.value = [...ids]
  }

  function resetPendingOrder(): void {
    dirtyOrder.value = []
  }

  return {
    items,
    editingId,
    draft,
    dirtyOrder,
    setItems,
    startCreate,
    startEdit,
    updateDraft,
    cancelEdit,
    setPendingOrder,
    resetPendingOrder,
  }
})