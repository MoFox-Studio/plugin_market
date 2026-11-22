<script setup lang="ts">
import { computed, ref } from 'vue';
import { categoryLabel } from '@/utils/format';
import AppIcon from '@/components/AppIcon.vue';
const props = withDefaults(
  defineProps<{
    categories: string[];
    modelValue?: string;
    target?: string;
    discovery?: boolean;
    loading?: boolean;
  }>(),
  { modelValue: '', target: 'market', discovery: false, loading: false },
);
defineEmits<{ 'update:modelValue': [value: string] }>();
const query = ref('');
const unique = computed(() => [
  ...new Set([
    ...props.categories,
    ...(props.modelValue ? [props.modelValue] : []),
  ]),
]);
const entries = computed(() =>
  unique.value
    .map((value, index) => ({ value, index, label: categoryLabel(value) }))
    .filter((item) =>
      (item.value + item.label)
        .toLowerCase()
        .includes(query.value.trim().toLowerCase()),
    ),
);
</script>
<template>
  <section
    class="category-index"
    :class="{ 'is-discovery': discovery }"
    aria-label="分类索引"
  >
    <header class="category-index__head">
      <div>
        <span>按用途查阅</span>
        <h2>{{ discovery ? '从一个用途开始。' : '分类索引' }}</h2>
      </div>
      <small>共 {{ unique.length }} 类</small>
    </header>
    <div v-if="!discovery && unique.length > 8" class="category-index__search">
      <AppIcon name="search" :size="14" /><input
        v-model="query"
        type="search"
        aria-label="查找分类"
        placeholder="定位分类…"
      />
    </div>
    <nav
      class="category-index__items"
      :aria-label="discovery ? '按用途浏览插件' : '筛选分类'"
    >
      <button
        v-if="!discovery"
        class="category-entry category-entry--all"
        :class="{ active: !modelValue }"
        :aria-pressed="!modelValue"
        @click="$emit('update:modelValue', '')"
      >
        <span class="category-entry__number">ALL</span
        ><span class="category-entry__copy"
          ><strong>全部内容</strong><small>查看所有分类</small></span
        ><span class="category-entry__arrow" aria-hidden="true">↗</span>
      </button>
      <component
        :is="discovery ? 'router-link' : 'button'"
        v-for="entry in entries"
        :key="entry.value"
        class="category-entry"
        :class="{ active: !discovery && modelValue === entry.value }"
        :to="
          discovery
            ? { name: target, query: { category: entry.value } }
            : undefined
        "
        :aria-pressed="discovery ? undefined : modelValue === entry.value"
        @click="!discovery && $emit('update:modelValue', entry.value)"
        ><span class="category-entry__number">{{
          String(entry.index + 1).padStart(2, '0')
        }}</span
        ><span class="category-entry__copy"
          ><strong>{{ entry.label }}</strong
          ><small>{{ entry.value }}</small></span
        ><span class="category-entry__arrow" aria-hidden="true"
          >↗</span
        ></component
      >
    </nav>
    <p v-if="loading && !unique.length" class="category-index__empty">
      正在读取分类…
    </p>
    <p v-else-if="query && !entries.length" class="category-index__empty">
      没有这个分类，试试其他名称。
    </p>
    <router-link
      v-if="discovery"
      class="category-index__all"
      :to="{ name: target }"
      >进入完整目录 <span aria-hidden="true">↗</span></router-link
    >
  </section>
</template>
<style scoped>
.category-index {
  min-width: 0;
}
.category-index__head {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 16px;
  padding-bottom: 18px;
  border-bottom: 3px double var(--line-strong);
}
.category-index__head span {
  font: 10px/1.5 var(--font-sans);
  letter-spacing: 0.08em;
  color: var(--blue-600);
}
.category-index__head h2 {
  margin: 7px 0 0;
  font: 700 22px/1.4 var(--font-editorial, serif);
  letter-spacing: -0.03em;
}
.category-index__head > small {
  font: 8px var(--font-mono);
  color: var(--ink-500);
  white-space: nowrap;
}
.category-index:not(.is-discovery) .category-index__head {
  display: grid;
  gap: 9px;
}
.category-index__search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 0;
  border-bottom: 1px solid var(--line);
  color: var(--ink-500);
}
.category-index__search input {
  width: 100%;
  min-width: 0;
  border: 0;
  background: transparent;
  font-size: 12px;
  padding: 0;
  outline-offset: 4px;
}
.category-index__items {
  display: grid;
}
.category-entry {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  padding: 17px 10px 17px 0;
  border-bottom: 1px solid var(--line);
  text-align: left;
  color: var(--ink-700);
  position: relative;
  transition:
    background var(--dur-fast),
    color var(--dur-fast);
}
.category-entry:before {
  content: '';
  position: absolute;
  left: -14px;
  top: 20%;
  bottom: 20%;
  width: 2px;
  background: var(--blue-500);
  opacity: 0;
}
.category-entry:hover {
  background: var(--blue-50);
  color: var(--blue-700);
}
.category-entry.active {
  background: var(--blue-50);
  color: var(--blue-700);
}
.category-entry.active:before {
  opacity: 1;
}
.category-entry__number {
  font: 9px var(--font-mono);
  color: var(--ink-500);
  flex: none;
  min-width: 24px;
}
.category-entry__copy {
  min-width: 0;
  display: grid;
  gap: 5px;
}
.category-entry__copy strong {
  font: 600 14px/1.4 var(--font-editorial, serif);
}
.category-entry__copy small {
  font: 8px/1.4 var(--font-mono);
  text-transform: uppercase;
  color: var(--ink-500);
  letter-spacing: 0.05em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.category-entry__arrow {
  margin-left: auto;
  font-size: 14px;
  color: var(--blue-600);
  opacity: 0.55;
}
.category-entry.active .category-entry__arrow {
  opacity: 1;
}
.category-index__empty {
  font-size: 12px;
  line-height: 1.8;
  color: var(--ink-500);
}
.is-discovery {
  padding: 32px 0 40px;
  border-bottom: 1px solid var(--line);
}
.is-discovery .category-index__head {
  border-bottom: 0;
  margin-bottom: 8px;
}
.is-discovery .category-index__head h2 {
  font-size: clamp(24px, 3vw, 34px);
}
.is-discovery .category-index__items {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border-top: 1px solid var(--line);
  border-left: 1px solid var(--line);
}
.is-discovery .category-entry {
  padding: 21px 18px;
  border-right: 1px solid var(--line);
}
.is-discovery .category-entry__number {
  align-self: start;
  padding-top: 3px;
}
.is-discovery .category-entry__copy strong {
  font-size: 14px;
}
.category-index__all {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: var(--blue-600);
  margin-top: 18px;
}
@media (max-width: 980px) {
  .category-index:not(.is-discovery) .category-index__head {
    display: flex;
  }
  .category-index:not(.is-discovery) .category-index__items {
    display: flex;
    overflow-x: auto;
    scrollbar-width: thin;
    gap: 8px;
    padding: 12px 0 5px;
  }
  .category-index:not(.is-discovery) .category-entry {
    min-width: 138px;
    padding: 12px;
    border: 1px solid var(--line);
    flex: none;
  }
  .category-index:not(.is-discovery) .category-entry__arrow {
    display: none;
  }
  .category-index:not(.is-discovery) .category-entry:before {
    left: -1px;
    top: -1px;
    bottom: -1px;
  }
  .category-index__search {
    max-width: 240px;
  }
  .is-discovery .category-index__items {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 620px) {
  .is-discovery .category-index__items {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .is-discovery .category-entry {
    padding: 17px 12px;
    gap: 8px;
  }
  .is-discovery .category-entry__number {
    min-width: 18px;
  }
  .is-discovery .category-index__head h2 {
    font-size: 22px;
  }
  .category-index__search input {
    font-size: 16px;
  }
}
</style>
