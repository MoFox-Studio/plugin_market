import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api'
import type { Skill } from '@/types'

export const useSkillsStore = defineStore('skills', () => {
  const skills = ref<Skill[]>([])
  const loading = ref(false)
  const search = ref('')
  const category = ref('')
  const tag = ref('')
  const sort = ref('updated')
  const page = ref(1)
  const pageSize = ref(20)
  const total = ref(0)
  const categories = ref<string[]>([])
  const tags = ref<string[]>([])

  async function loadSkills() {
    loading.value = true
    try {
      const params: Record<string, string | number | boolean | null | undefined> = {
        page: page.value,
        page_size: pageSize.value,
        sort: sort.value,
      }
      if (search.value) params.search = search.value
      if (category.value) params.category = category.value
      if (tag.value) params.tag = tag.value
      const res = await api.skills.list(params)
      skills.value = res.items
      total.value = res.total
    } catch {
      skills.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  async function loadCategories() {
    try {
      categories.value = await api.skills.categories()
    } catch {
      categories.value = []
    }
  }

  async function loadTags() {
    try {
      tags.value = await api.skills.tags()
    } catch {
      tags.value = []
    }
  }

  function setFilter(f: { search?: string; category?: string; tag?: string; sort?: string }) {
    if (f.search !== undefined) search.value = f.search
    if (f.category !== undefined) category.value = f.category
    if (f.tag !== undefined) tag.value = f.tag
    if (f.sort !== undefined) sort.value = f.sort
    page.value = 1
    loadSkills()
  }

  function setPage(p: number) {
    page.value = p
    loadSkills()
  }

  return {
    skills, loading, search, category, tag, sort, page, pageSize, total, categories, tags,
    loadSkills, loadCategories, loadTags, setFilter, setPage,
  }
})
