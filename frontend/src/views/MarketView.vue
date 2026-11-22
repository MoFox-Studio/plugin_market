<script setup lang="ts">
import MarketSelect from '@/components/MarketSelect.vue';
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import api from '@/api';
import { useAuthStore } from '@/stores/auth';
import { useTaxonomyStore } from '@/stores/taxonomy';
import { categoryLabel } from '@/utils/format';
import type { Plugin } from '@/types';
import PluginCard from '@/components/PluginCard.vue';
import AppIcon from '@/components/AppIcon.vue';
import CatalogFrame from '@/components/catalog/CatalogFrame.vue';
import CatalogMasthead from '@/components/catalog/CatalogMasthead.vue';
import CategoryIndex from '@/components/catalog/CategoryIndex.vue';
import MarketTopicGroups from '@/components/catalog/MarketTopicGroups.vue';
import CatalogState from '@/components/catalog/CatalogState.vue';
import { useCatalogResource } from '@/components/catalog/useCatalogResource';
const route = useRoute(),
  router = useRouter(),
  auth = useAuthStore(),
  taxonomy = useTaxonomyStore();
const results = useCatalogResource(() => ({ items: [] as Plugin[], total: 0, loadedPage: 0 }));
const initialLoading = computed(() => results.loading && !results.data.loadedPage);
const search = ref('');
const value = (key: string, fallback = '') =>
  typeof route.query[key] === 'string'
    ? (route.query[key] as string)
    : fallback;
const query = computed(() => value('q').trim());
const category = computed(() => value('category')),
  tag = computed(() => value('tag')),
  trust = computed(() => value('trust_level'));
const sort = computed(() =>
  ['updated', 'popular', 'rating', 'downloads', 'likes', 'trending'].includes(
    value('sort'),
  )
    ? value('sort')
    : 'updated',
);
const view = computed(() => (value('view') === 'list' ? 'list' : 'grid'));
const page = computed(() => {
  const n = Number(value('page', '1'));
  return Number.isSafeInteger(n) && n > 0 ? n : 1;
});
const displayedPage = computed(() => results.data.loadedPage || page.value);
const pageSize = 24,
  totalPages = computed(() =>
    Math.max(1, Math.ceil(results.data.total / pageSize)),
  );
const hasFilters = computed(
  () => !!(query.value || category.value || tag.value || trust.value),
);
const pageRange = computed(() => {
  const out: number[] = [];
  const total = totalPages.value,
    current = displayedPage.value;
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  out.push(1);
  if (current > 3) out.push(-1);
  for (
    let n = Math.max(2, current - 1);
    n <= Math.min(total - 1, current + 1);
    n++
  )
    out.push(n);
  if (current < total - 2) out.push(-1);
  out.push(total);
  return out;
});
function filter(partial: Record<string, string>) {
  const next = { ...route.query, ...partial };
  for (const [key, val] of Object.entries(next)) if (!val) delete next[key];
  void router.push({ name: 'market', query: next });
}
function clearFilters() {
  void router.push({
    name: 'market',
    query: view.value === 'list' ? { view: 'list' } : {},
  });
}
async function load() {
  const requestedPage = page.value;
  const params = new URLSearchParams({
    limit: String(pageSize),
    offset: String((page.value - 1) * pageSize),
    sort: sort.value,
  });
  if (query.value) params.set('q', query.value);
  if (category.value) params.set('category', category.value);
  if (tag.value) params.set('tag', tag.value);
  if (trust.value) params.set('trust_level', trust.value);
  const key = route.fullPath;
  await results.load(async () => ({
    ...await api.get<{ items: Plugin[]; total: number }>(`/api/v1/plugins?${params}`),
    loadedPage: requestedPage,
  }));
  if (key === route.fullPath && !results.loading && !results.error && page.value > totalPages.value)
    void router.replace({
      query: { ...route.query, page: String(totalPages.value) },
    });
}
watch(
  [() => auth.viewer?.author_id, query, category, tag, trust, sort, page],
  ([viewer], previous) => {
    if (viewer !== previous?.[0]) results.reset();
    search.value = query.value;
    void load();
  },
  { immediate: true },
);
onMounted(() => {
  void taxonomy.load();
});
</script>
<template>
  <CatalogFrame class="archive-page">
    <CatalogMasthead
      title="插件总目"

      description="按用途、来源与标签查阅社区发布的插件。"
    >
        <div class="query-console">
          <form
            class="catalog-search"
            role="search"
            @submit.prevent="filter({ q: search.trim(), page: '1' })"
          >
            <AppIcon name="search" /><input
              v-model="search"
              type="search"
              aria-label="搜索插件"
              placeholder="搜索插件名称、作者或用途…"
            /><button class="btn btn-primary" type="submit">检索插件 ↗</button>
          </form>
          <div class="catalog-toolbar">
            <div class="catalog-controls">
              <label
                >来源<MarketSelect
                  :value="trust"
                  @change="
                    filter({
                      trust_level: ($event.target as HTMLSelectElement).value,
                      page: '1',
                    })
                  "
                >
                  <option value="">全部来源</option>
                  <option value="official">官方</option>
                  <option value="verified">认证</option>
                  <option value="community">社区</option>
                </MarketSelect></label
              ><label v-if="taxonomy.tags.length"
                >标签<MarketSelect
                  :value="tag"
                  @change="
                    filter({
                      tag: ($event.target as HTMLSelectElement).value,
                      page: '1',
                    })
                  "
                >
                  <option value="">全部标签</option>
                  <option v-for="t in taxonomy.tags" :key="t">{{ t }}</option>
                </MarketSelect></label
              ><button
                v-if="hasFilters"
                class="btn btn-ghost btn-sm"
                @click="clearFilters"
              >
                清除筛选 ×
              </button>
            </div>
            <div class="catalog-controls">
              <label
                >排序<MarketSelect
                  :value="sort"
                  @change="
                    filter({
                      sort: ($event.target as HTMLSelectElement).value,
                      page: '1',
                    })
                  "
                >
                  <option value="updated">最近更新</option>
                  <option value="popular">综合热度</option>
                  <option value="rating">评分最高</option>
                  <option value="downloads">下载最多</option>
                  <option value="likes">订阅最多</option>
                  <option value="trending">趋势上升</option>
                </MarketSelect></label
              >
              <div class="catalog-segment">
                <button
                  :class="{ active: view === 'grid' }"
                  :aria-pressed="view === 'grid'"
                  @click="filter({ view: 'grid' })"
                >
                  网格</button
                ><button
                  :class="{ active: view === 'list' }"
                  :aria-pressed="view === 'list'"
                  @click="filter({ view: 'list' })"
                >
                  列表
                </button>
              </div>
            </div>
          </div>

          <div v-if="hasFilters" class="query-selection" aria-label="已选条件">
            <span>当前条件</span
            ><button v-if="query" @click="filter({ q: '', page: '1' })">
              关键词 / {{ query }} <b>×</b></button
            ><button
              v-if="category"
              :aria-label="`移除分类 ${categoryLabel(category)}`"
              @click="filter({ category: '', page: '1' })"
            >
              {{ categoryLabel(category) }} <b>×</b></button
            ><button v-if="tag" @click="filter({ tag: '', page: '1' })">
              #{{ tag }} <b>×</b></button
            ><button
              v-if="trust"
              @click="filter({ trust_level: '', page: '1' })"
            >
              来源 /
              {{
                trust === 'official'
                  ? '官方'
                  : trust === 'verified'
                    ? '认证'
                    : '社区'
              }}
              <b>×</b>
            </button>
          </div>
        </div>
    </CatalogMasthead>
    <div class="catalog-workspace">
      <aside class="catalog-filter-rail">
        <CategoryIndex
          :loading="taxonomy.loading"
          :categories="taxonomy.categories"
          :model-value="category"
          @update:model-value="filter({ category: $event, page: '1' })"
        />
        <MarketTopicGroups
          :tags="taxonomy.tags"
          :model-value="tag"
          @update:model-value="filter({ tag: $event, page: '1' })"
        />
        <div v-if="taxonomy.error" class="workspace-filter-error" role="status">
          {{ taxonomy.error
          }}<button class="catalog-link" @click="taxonomy.load(true)">
            重新加载筛选项
          </button>
        </div>
        <div class="workspace-guide">
          <span>检索说明</span>
          <p>
            分类与关键词可以组合使用。已选条件会保留在链接里，方便继续探索与分享。
          </p>
          <router-link to="/skills">发现更多 Skills ↗</router-link>
        </div>
      </aside>
      <section class="catalog-results" aria-label="插件检索结果" :aria-busy="results.loading">
        <div class="workspace-result-head">
          <div>
            <span class="edition-index-label">本版目录</span>
            <h2>
              {{ category ? categoryLabel(category) : '全部插件'
              }}<small>{{ initialLoading || results.error ? '—' : results.data.total }} 项</small>
            </h2>
          </div>
          <p class="catalog-caption" aria-live="polite">
            {{
              results.loading
                ? initialLoading ? '正在同步档案…' : '正在更新检索结果…'
                : results.error
                  ? '检索未完成'
                  : '第 ' + page + ' 页 / 共 ' + totalPages + ' 页'
            }}
          </p>
        </div>
        <CatalogState
          :loading="initialLoading"
          :error="results.error"
          :empty="!results.data.items.length"
          cards
          title="没有找到匹配的插件"
          message="试试其他关键词，或清除筛选再看看。"
          @retry="load"
          ><template #empty-action
            ><button v-if="hasFilters" class="btn" @click="clearFilters">
              浏览全部插件
            </button></template
          >
          <div class="catalog-grid edition-index" :class="{ 'list-view': view === 'list' }">
            <PluginCard
              v-for="(plugin, index) in results.data.items"
              :key="plugin.plugin_id"
              :plugin="plugin"
              :number="(results.data.loadedPage - 1) * pageSize + index + 1"
              :lead="index === 0 && view === 'grid'"
              :compact="view === 'list'"
            /></div
        ></CatalogState>
        <nav
          v-if="!results.error && totalPages > 1"
          class="catalog-pagination"
          aria-label="插件分页"
        >
          <button
            class="btn btn-sm"
            :disabled="results.loading || page <= 1"
            @click="filter({ page: String(page - 1) })"
          >
            上一页</button
          ><template v-for="(n, index) in pageRange" :key="index"
            ><span v-if="n === -1">…</span
            ><button
              v-else
              class="page-number"
              :disabled="results.loading"
              :class="{ active: n === displayedPage }"
              :aria-current="n === displayedPage ? 'page' : undefined"
              @click="filter({ page: String(n) })"
            >
              {{ n }}
            </button></template
          ><button
            class="btn btn-sm"
            :disabled="results.loading || page >= totalPages"
            @click="filter({ page: String(page + 1) })"
          >
            下一页
          </button>
        </nav>
      </section>
    </div>
  </CatalogFrame>
</template>
