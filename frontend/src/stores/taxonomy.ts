import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api'

export const useTaxonomyStore = defineStore('taxonomy', () => {
  const categories = ref<string[]>([])
  const tags = ref<string[]>([])
  const loaded = ref(false)

  async function load(force = false): Promise<void> {
    if (!force && loaded.value) return
    const [c, t] = await Promise.all([
      api.get<{ items: string[] }>('/api/v1/categories').catch(() => ({ items: [] as string[] })),
      api.get<{ items: string[] }>('/api/v1/tags').catch(() => ({ items: [] as string[] })),
    ])
    categories.value = c.items || []
    tags.value = t.items || []
    loaded.value = true
  }

  return { categories, tags, loaded, load }
})
