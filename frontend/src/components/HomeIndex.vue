<script setup lang="ts">
import { useRouter } from 'vue-router';
import AppIcon from './AppIcon.vue';
import MarketSelect from './MarketSelect.vue';
import { categoryLabel } from '@/utils/format';

defineProps<{ categories: string[] }>();
const router = useRouter();
function browsePurpose(value: string | number) {
  void router.push({ name: 'market', query: { category: String(value) } });
}
</script>

<template>
  <section class="home-index" aria-labelledby="home-index-title">
    <header class="home-index__heading">
      <span>索引</span>
      <h2 id="home-index-title">浏览插件与技能</h2>
    </header>
    <nav class="home-index__actions" aria-label="索引浏览方式">
      <MarketSelect
        v-if="categories.length"
        class="home-index__purpose"
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
      <router-link class="home-index__skills" to="/skills">
        <span>浏览技能</span><AppIcon name="arrow" :size="15" />
      </router-link>
    </nav>
  </section>
</template>

<style scoped>
.home-index {
  display: grid;
  grid-template-columns: minmax(160px, 0.45fr) minmax(0, 1fr);
  align-items: center;
  gap: 16px clamp(18px, 3vw, 42px);
  margin-top: clamp(18px, 2.2vw, 32px);
  padding-block: 14px;
  border-block: 3px double var(--ink-500);
  background: var(--surface);
}
.home-index__heading {
  display: grid;
  gap: 5px;
}
.home-index__heading > span {
  color: var(--blue-700);
  font: 600 12px/1.4 var(--font-mono);
  letter-spacing: 0.15em;
}
.home-index__heading h2 {
  margin: 0;
  font: 700 clamp(20px, 1.6vw, 25px) / 1.3 var(--font-editorial);
  letter-spacing: -0.025em;
  text-wrap: balance;
}
.home-index__actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.home-index__actions :deep(.market-select) {
  display: block;
  width: 100%;
  min-width: 0;
  max-width: none;
}
.home-index__actions :deep(.market-select-trigger),
.home-index__skills {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  min-width: 0;
  min-height: 48px;
  padding: 10px 14px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--ink-700);
  font: 600 14px/1.4 var(--font-sans);
  text-align: start;
  text-decoration: none;
  white-space: nowrap;
}
.home-index__actions :deep(.market-select-trigger:hover),
.home-index__skills:hover {
  border-color: var(--blue-500);
  background: var(--surface-soft);
  color: var(--blue-700);
}
.home-index__skills:focus-visible {
  outline: 3px solid var(--blue-500);
  outline-offset: 3px;
}
.home-index__actions :deep(.market-select-chevron) {
  flex: none;
  color: var(--blue-700);
}
@media (max-width: 940px) {
  .home-index {
    grid-template-columns: minmax(0, 1fr);
    gap: 10px;
  }
  .home-index__heading {
    display: flex;
    align-items: baseline;
    gap: 10px;
  }
}
@media (max-width: 560px) {
  .home-index {
    padding-block: 12px;
  }
  .home-index__heading {
    align-items: start;
    flex-direction: column;
    gap: 4px;
  }
  .home-index__actions {
    gap: 7px;
  }
  .home-index__actions :deep(.market-select-trigger),
  .home-index__skills {
    min-height: 44px;
    padding-inline: 10px;
    font-size: 12px;
  }
}
</style>
