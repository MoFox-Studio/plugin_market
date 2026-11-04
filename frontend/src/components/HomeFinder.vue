<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import AppIcon from './AppIcon.vue';
import MarketSelect from './MarketSelect.vue';
import { categoryLabel } from '@/utils/format';

defineProps<{ categories: string[] }>();
const router = useRouter();
const query = ref('');
function search() {
  const q = query.value.trim();
  void router.push({ name: 'market', query: q ? { q } : {} });
}
function browsePurpose(value: string | number) {
  void router.push({ name: 'market', query: { category: String(value) } });
}
</script>

<template>
  <div class="home-finder">
    <form
      class="finder-form"
      role="search"
      aria-label="首页插件搜索"
      @submit.prevent="search"
    >
      <AppIcon name="search" :size="18" />
      <input
        v-model="query"
        type="search"
        name="q"
        aria-label="搜索插件名称或功能"
        placeholder="插件名或功能，如天气"
      />
      <button type="submit">搜索 <AppIcon name="arrow" :size="15" /></button>
    </form>
    <nav class="finder-entries" aria-label="发现插件与技能">
      <router-link class="finder-all" to="/browse">
        <AppIcon name="grid" :size="16" />
        <span>全部插件</span>
        <AppIcon name="arrow" :size="15" />
      </router-link>
      <MarketSelect
        v-if="categories.length"
        placeholder="按用途找插件"
        aria-label="按用途找插件"
        @update:model-value="browsePurpose"
      >
        <option
          v-for="category in categories"
          :key="category"
          :value="category"
        >
          {{ categoryLabel(category) }}
        </option>
      </MarketSelect>
      <router-link class="finder-skills" to="/skills"
        >发现技能 <span aria-hidden="true">↗</span></router-link
      >
    </nav>
  </div>
</template>

<style scoped>
.home-finder {
  max-width: 430px;
  min-width: 0;
}
.finder-form {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 6px 7px 6px 14px;
  background: var(--surface);
  color: var(--ink-500);
  border: 1px solid var(--line-strong);
  border-left: 3px solid var(--blue-700);
}
.finder-form:focus-within {
  outline: 2px solid var(--blue-500);
  outline-offset: 2px;
}
.finder-form input {
  min-width: 0;
  width: 100%;
  height: 34px;
  padding: 0;
  border: 0;
  outline: 0;
  color: var(--ink-900);
  background: transparent;
  font: inherit;
}
.finder-form button {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 7px 0 12px;
  border: 0;
  border-left: 1px solid var(--line-strong);
  background: transparent;
  color: var(--blue-700);
  font-weight: 700;
}
.finder-form button:hover { text-decoration: underline; text-underline-offset: 3px; }
.finder-entries {
  display: flex;
  align-items: center;
  gap: 4px 14px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.finder-entries a,
.finder-entries :deep(.market-select-trigger) {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  width: auto;
  min-height: 42px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--ink-700);
  font: 600 13px/1.4 var(--font-sans);
  white-space: nowrap;
}
.finder-entries :deep(.market-select),
.finder-entries :deep(.market-select-trigger) {
  width: auto;
  min-width: 0;
}
.finder-entries .finder-all {
  gap: 8px;
  padding-inline: 14px;
  border-radius: 2px;
  background: var(--blue-700);
  color: var(--ink-on-blue);
  font-size: 14px;
  font-weight: 700;
}
.finder-entries .finder-all:hover { background: var(--blue-900); }
.finder-skills span,
.finder-entries :deep(.market-select-chevron) {
  color: var(--blue-700);
}
.finder-skills:hover,
.finder-entries :deep(.market-select-trigger:hover) {
  color: var(--blue-700);
  text-decoration: underline;
  text-underline-offset: 4px;
}
@media (max-width: 700px) {
  .finder-form input {
    height: 44px;
    font-size: 16px;
  }
  .finder-form {
    gap: 6px;
    padding: 3px 4px 3px 9px;
  }
  .finder-form button,
  .finder-entries a,
  .finder-entries :deep(.market-select-trigger) {
    min-height: 44px;
  }
  .finder-entries {
    gap: 3px 10px;
    margin-top: 9px;
  }
  .finder-entries .finder-all { gap: 6px; padding-inline: 10px; }
}
</style>
