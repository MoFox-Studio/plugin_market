import { defineStore } from 'pinia';
import { ref } from 'vue';
import api from '@/api';
export const useTaxonomyStore = defineStore('taxonomy', () => {
  const categories = ref<string[]>([]);
  const tags = ref<string[]>([]);
  const loaded = ref(false);
  const loading = ref(false);
  const error = ref('');
  let pending: Promise<void> | null = null;
  let generation = 0;
  function load(force = false): Promise<void> {
    if (pending && !force) return pending;
    if (loaded.value && !force) return Promise.resolve();
    const id = ++generation;
    loading.value = true;
    error.value = '';
    pending = (async () => {
      const [c, t] = await Promise.allSettled([
        api.get<{ items: string[] }>('/api/v1/categories'),
        api.get<{ items: string[] }>('/api/v1/tags'),
      ]);
      if (id !== generation) return;
      const failures: string[] = [];
      if (c.status === 'fulfilled') categories.value = c.value.items || [];
      else failures.push('分类');
      if (t.status === 'fulfilled') tags.value = t.value.items || [];
      else failures.push('标签');
      loaded.value = failures.length === 0;
      error.value = failures.length
        ? failures.join('与') + '暂时无法读取，请重试。'
        : '';
      loading.value = false;
      pending = null;
    })();
    return pending;
  }
  return { categories, tags, loaded, loading, error, load };
});
