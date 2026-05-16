import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { MentionCandidate } from '@/types'

const MAX_CACHE_ENTRIES = 20

export const useMentionsStore = defineStore('mentions', () => {
  const cache = ref<Record<string, MentionCandidate[]>>({})
  const lruKeys = ref<string[]>([])

  function touch(prefix: string): void {
    lruKeys.value = [
      prefix,
      ...lruKeys.value.filter((item) => item !== prefix),
    ].slice(0, MAX_CACHE_ENTRIES)

    const allowed = new Set(lruKeys.value)
    cache.value = Object.fromEntries(
      Object.entries(cache.value).filter(([key]) => allowed.has(key))
    )
  }

  function getCached(prefix: string): MentionCandidate[] {
    const normalized = prefix.trim().toLowerCase()
    if (!normalized || !cache.value[normalized]) {
      return []
    }
    touch(normalized)
    return cache.value[normalized]
  }

  function remember(prefix: string, candidates: MentionCandidate[]): MentionCandidate[] {
    const normalized = prefix.trim().toLowerCase()
    if (!normalized) {
      return []
    }
    cache.value = {
      ...cache.value,
      [normalized]: candidates,
    }
    touch(normalized)
    return candidates
  }

  async function resolve(
    prefix: string,
    loader?: (prefix: string) => Promise<MentionCandidate[]>,
  ): Promise<MentionCandidate[]> {
    const normalized = prefix.trim().toLowerCase()
    if (!normalized) {
      return []
    }

    const cached = getCached(normalized)
    if (cached.length || loader === undefined) {
      return cached
    }

    const loaded = await loader(normalized)
    return remember(normalized, loaded)
  }

  function clear(): void {
    cache.value = {}
    lruKeys.value = []
  }

  return {
    cache,
    lruKeys,
    getCached,
    remember,
    resolve,
    clear,
  }
})