<script setup lang="ts">
import MarketSelect from '@/components/MarketSelect.vue';
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import api from '@/api';
import { useAuthStore } from '@/stores/auth';
import { categoryLabel, formatNumber, formatRelative } from '@/utils/format';
import type { Skill } from '@/types';
import CatalogFrame from '@/components/catalog/CatalogFrame.vue';
import CatalogMasthead from '@/components/catalog/CatalogMasthead.vue';
import CatalogListing from '@/components/catalog/CatalogListing.vue';
import CategoryIndex from '@/components/catalog/CategoryIndex.vue';
import AppIcon from '@/components/AppIcon.vue';
import CatalogState from '@/components/catalog/CatalogState.vue';
import { useCatalogResource } from '@/components/catalog/useCatalogResource';
const route = useRoute(),
  router = useRouter(),
  auth = useAuthStore(),
  search = ref('');
const results = useCatalogResource(() => ({ items: [] as Skill[], total: 0, loadedPage: 0 }));
const initialLoading = computed(() => results.loading && !results.data.loadedPage);
const categories = useCatalogResource<string[]>(() => []),
  tags = useCatalogResource<string[]>(() => []);
const value = (key: string, fallback = '') =>
  typeof route.query[key] === 'string'
    ? (route.query[key] as string)
    : fallback;
const query = computed(() => value('q', value('search')).trim()),
  category = computed(() => value('category')),
  tag = computed(() => value('tag'));
const sort = computed(() =>
  ['updated', 'created', 'downloads', 'name'].includes(value('sort'))
    ? value('sort')
    : 'updated',
);
const view = computed(() => (value('view') === 'list' ? 'list' : 'grid'));
const page = computed(() => {
  const n = Number(value('page', '1'));
  return Number.isSafeInteger(n) && n > 0 ? n : 1;
});
const pageSize = 24,
  totalPages = computed(() =>
    Math.max(1, Math.ceil(results.data.total / pageSize)),
  );
const filtered = computed(() => !!(query.value || category.value || tag.value));
function filter(partial: Record<string, string>) {
  const next = { ...route.query, ...partial };
  delete next.search;
  for (const [key, val] of Object.entries(next)) if (!val) delete next[key];
  void router.push({ name: 'skills', query: next });
}
function clear() {
  void router.push({
    name: 'skills',
    query: view.value === 'list' ? { view: 'list' } : {},
  });
}
async function load() {
  const params = {
      search: query.value,
      category: category.value,
      tag: tag.value,
      sort: sort.value,
      page: page.value,
      page_size: pageSize,
    },
    key = route.fullPath;
  await results.load(async () => ({ ...await api.skills.list(params), loadedPage: params.page }));
  if (key === route.fullPath && !results.loading && !results.error && page.value > totalPages.value)
    void router.replace({
      query: { ...route.query, page: String(totalPages.value) },
    });
}
watch(
  [() => auth.viewer?.author_id, query, category, tag, sort, page],
  ([viewer], previous) => {
    if (viewer !== previous?.[0]) results.reset();
    search.value = query.value;
    void load();
  },
  { immediate: true },
);
onMounted(() => {
  void categories.load(api.skills.categories);
  void tags.load(api.skills.tags);
});
</script>
<template>
  <CatalogFrame class="archive-page">
    <CatalogMasthead
      title="技能总目"

      description="查阅社区技能、使用说明与可获取的技能包。"
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
              placeholder="搜索技能名称、描述或用途…"
              aria-label="搜索 Skills"
            /><button class="btn btn-primary" type="submit">检索技能 ↗</button>
          </form>
          <div class="catalog-toolbar">
            <div class="catalog-controls">
              <label v-if="tags.data.length"
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
                  <option v-for="t in tags.data" :key="t">{{ t }}</option>
                </MarketSelect></label
              ><button
                v-if="filtered"
                class="btn btn-ghost btn-sm"
                @click="clear"
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
                  <option value="downloads">下载最多</option>
                  <option value="created">最新发布</option>
                  <option value="name">名称排序</option>
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

          <div v-if="filtered" class="query-selection" aria-label="已选条件">
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
              #{{ tag }} <b>×</b>
            </button>
          </div>
        </div>
    </CatalogMasthead>
    <div class="catalog-workspace">
      <aside class="catalog-filter-rail">
        <CategoryIndex
          :loading="categories.loading"
          :categories="categories.data"
          :model-value="category"
          @update:model-value="filter({ category: $event, page: '1' })"
        />
        <div
          v-if="categories.error || tags.error"
          class="workspace-filter-error"
          role="status"
        >
          筛选索引暂未同步。<button
            class="catalog-link"
            @click="
              categories.load(api.skills.categories);
              tags.load(api.skills.tags);
            "
          >
            重新加载
          </button>
        </div>
        <div class="workspace-guide">
          <span>检索说明</span>
          <p>
            分类与关键词可以组合使用。已选条件会保留在链接里，方便继续探索与分享。
          </p>
          <router-link to="/browse">探索插件目录 ↗</router-link>
        </div>
      </aside>
      <section class="catalog-results" aria-label="技能检索结果" :aria-busy="results.loading">
        <div class="workspace-result-head">
          <div>
            <span class="edition-index-label">本版目录</span>
            <h2>
              {{ category ? categoryLabel(category) : '全部技能'
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
          title="没有找到匹配的 Skill"
          message="试试其他关键词或分类，也可以发布自己的技能模块。"
          @retry="load"
          ><template #empty-action
            ><button v-if="filtered" class="btn" @click="clear">清除筛选</button
            ><router-link v-else class="btn" to="/me"
              >前往工作台 ↗</router-link
            ></template
          >
          <div class="catalog-grid edition-index" :class="{ 'list-view': view === 'list' }">
            <CatalogListing
              v-for="(skill, index) in results.data.items"
              :key="skill.skill_id"
              :to="{ name: 'skill', params: { id: skill.skill_id } }"
              :number="(results.data.loadedPage - 1) * pageSize + index + 1"
              :lead="index === 0 && view === 'grid'"
              :compact="view === 'list'"
              :title="skill.display_name"
              :description="skill.description"
              :author="skill.owner_display_name || skill.owner_login || skill.owner_id"
              :icon="skill.icon_url"
              :version="skill.latest_version" :categories="skill.categories" :tags="skill.tags"
              :labels="(skill.categories || []).slice(0, 2).map(categoryLabel)"
            >
              <span v-market-tooltip="'下载次数'"><AppIcon name="download" :size="13" />{{ formatNumber(skill.download_count) }}</span>
              <span v-if="skill.rating_count">★ {{ Number(skill.rating_avg || 0).toFixed(1) }}</span>
              <time :datetime="skill.updated_at">{{ formatRelative(skill.updated_at) }}</time>
            </CatalogListing>
          </div></CatalogState
        >
        <nav
          v-if="!results.error && totalPages > 1"
          class="catalog-pagination"
          aria-label="Skills 分页"
        >
          <button
            class="btn btn-sm"
            :disabled="results.loading || page <= 1"
            @click="filter({ page: String(page - 1) })"
          >
            上一页</button
            ><span class="catalog-caption">{{ results.data.loadedPage || page }} / {{ totalPages }}</span
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
