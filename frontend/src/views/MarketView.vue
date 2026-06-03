<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import { useTaxonomyStore } from '@/stores/taxonomy'
import { categoryLabel } from '@/utils/format'
import type { Plugin } from '@/types'
import PluginCard from '@/components/PluginCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import VolKickerBar from '@/components/VolKickerBar.vue'

const route = useRoute()
const router = useRouter()
const taxonomy = useTaxonomyStore()

const sort = ref('updated')
const category = ref('')
const tag = ref('')
const trust = ref('')
const view = ref<'grid' | 'list'>('grid')
const query = ref('')

const plugins = ref<Plugin[]>([])
const total = ref(0)
const loading = ref(true)
const page = ref(1)
const pageSize = 36
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const pageRange = computed(() => {
  const tp = totalPages.value
  const cur = page.value
  if (tp <= 7) return Array.from({ length: tp }, (_, i) => i + 1)
  const pages: number[] = [1]
  const start = Math.max(2, cur - 1)
  const end = Math.min(tp - 1, cur + 1)
  if (start > 2) pages.push(-1)
  for (let i = start; i <= end; i++) pages.push(i)
  if (end < tp - 1) pages.push(-1)
  pages.push(tp)
  return pages
})

const hasFilters = computed(() => !!(query.value || category.value || tag.value || trust.value))

const filterSummary = computed(() => {
  const parts: string[] = []
  if (query.value) parts.push(`关键字 "${query.value}"`)
  if (category.value) parts.push(`分类 ${categoryLabel(category.value)}`)
  if (tag.value) parts.push(`标签 #${tag.value}`)
  if (trust.value) {
    const map: Record<string, string> = { official: '官方', verified: '认证', community: '社区' }
    parts.push(`${map[trust.value] || trust.value} 插件`)
  }
  return parts.length ? parts.join(' · ') : '浏览所有已发布的插件，按状态、分类、标签和信任等级筛选。'
})

async function loadPlugins() {
  loading.value = true
  const p = new URLSearchParams()
  p.set('limit', String(pageSize))
  p.set('offset', String((page.value - 1) * pageSize))
  p.set('sort', sort.value)
  if (query.value) p.set('q', query.value)
  if (category.value) p.set('category', category.value)
  if (tag.value) p.set('tag', tag.value)
  if (trust.value) p.set('trust_level', trust.value)
  try {
    const result = await api.get<{ items: Plugin[]; total: number }>(`/api/v1/plugins?${p.toString()}`)
    plugins.value = result.items || []
    total.value = result.total || 0
  } catch {
    plugins.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function routeValue(key: string, fallback = ''): string {
  const value = route.query[key]
  return typeof value === 'string' ? value : fallback
}

function pushFilters(partial: Record<string, string>): void {
  const merged: Record<string, string> = {
    q: query.value,
    category: category.value,
    tag: tag.value,
    trust_level: trust.value,
    sort: sort.value,
    view: view.value,
    page: String(page.value),
    ...partial,
  }
  const nextQuery: Record<string, string> = {}
  for (const [k, v] of Object.entries(merged)) if (v) nextQuery[k] = v
  void router.push({ name: 'market', query: nextQuery })
}

function setCategory(cat: string) { pushFilters({ category: cat, page: '1' }) }
function setTag(t: string) { pushFilters({ tag: t, page: '1' }) }
function setTrust(t: string) { pushFilters({ trust_level: t, page: '1' }) }
function setSort(s: string) { pushFilters({ sort: s, page: '1' }) }
function resetFilters() { pushFilters({ q: '', category: '', tag: '', trust_level: '', sort: 'updated', view: view.value, page: '1' }) }
function setPage(p: number) { pushFilters({ page: String(p) }) }

watch(
  () => [route.query.q, route.query.category, route.query.tag, route.query.trust_level, route.query.sort, route.query.view, route.query.page],
  () => {
    query.value = routeValue('q')
    category.value = routeValue('category')
    tag.value = routeValue('tag')
    trust.value = routeValue('trust_level')
    sort.value = routeValue('sort', 'updated')
    view.value = (routeValue('view', 'grid') as 'grid' | 'list')
    page.value = Math.max(1, parseInt(routeValue('page', '1'), 10) || 1)
    void loadPlugins()
  },
  { immediate: true },
)

onMounted(async () => {
  await taxonomy.load()
})
</script>

<template>
  <VolKickerBar :page-label="'BROWSE'" :count="total" />

  <div class="browse-page">
    <aside class="browse-side">
      <div class="browse-side-section">
        <h4>排序</h4>
        <ul>
          <li><button type="button" :class="{ active: sort === 'updated' }" @click="setSort('updated')">最近更新</button></li>
          <li><button type="button" :class="{ active: sort === 'popular' }" @click="setSort('popular')">综合热度</button></li>
          <li><button type="button" :class="{ active: sort === 'rating' }" @click="setSort('rating')">高分好评</button></li>
          <li><button type="button" :class="{ active: sort === 'downloads' }" @click="setSort('downloads')">下载最多</button></li>
          <li><button type="button" :class="{ active: sort === 'trending' }" @click="setSort('trending')">趋势上升</button></li>
        </ul>
      </div>

      <div class="browse-side-section">
        <h4>分类</h4>
        <ul>
          <li><button type="button" :class="{ active: !category }" @click="setCategory('')">全部分类</button></li>
          <li v-for="cat in taxonomy.categories" :key="cat">
            <button type="button" :class="{ active: category === cat }" @click="setCategory(cat)">{{ categoryLabel(cat) }}</button>
          </li>
        </ul>
      </div>

      <div class="browse-side-section">
        <h4>信任等级</h4>
        <ul>
          <li><button type="button" :class="{ active: !trust }" @click="setTrust('')">全部</button></li>
          <li><button type="button" :class="{ active: trust === 'official' }" @click="setTrust('official')">官方 / 公式</button></li>
          <li><button type="button" :class="{ active: trust === 'verified' }" @click="setTrust('verified')">认证 / 認定</button></li>
          <li><button type="button" :class="{ active: trust === 'community' }" @click="setTrust('community')">社区 / 同人</button></li>
        </ul>
      </div>

      <div class="browse-side-section" v-if="taxonomy.tags.length">
        <h4>热门标签</h4>
        <ul>
          <li><button type="button" :class="{ active: !tag }" @click="setTag('')">全部标签</button></li>
          <li v-for="t in taxonomy.tags.slice(0, 30)" :key="t">
            <button type="button" :class="{ active: tag === t }" @click="setTag(t)">#{{ t }}</button>
          </li>
        </ul>
      </div>
    </aside>

    <main class="browse-main">
      <div class="browse-crumb">
        <router-link to="/" class="browse-crumb-link">推荐</router-link>
        <span class="browse-crumb-sep">/</span>
        <span class="browse-crumb-text">浏览</span>
        <template v-if="hasFilters">
          <span class="browse-crumb-sep">/</span>
          <span class="browse-crumb-active">{{ filterSummary }}</span>
        </template>
      </div>

      <header class="browse-head">
        <div class="browse-head-titles">
          <h1>全部插件</h1>
          <p>{{ filterSummary }}</p>
        </div>
        <div class="browse-head-count">
          <strong>{{ total }}</strong>
          <small>个结果</small>
        </div>
      </header>

      <div class="browse-toolbar">
        <div class="browse-toolbar-left">
          <select :value="sort" @change="setSort(($event.target as HTMLSelectElement).value)">
            <option value="updated">最近更新</option>
            <option value="popular">综合热度</option>
            <option value="rating">评分优先</option>
            <option value="downloads">下载最多</option>
            <option value="likes">订阅最多</option>
            <option value="trending">趋势上升</option>
          </select>
          <div class="chip-group">
            <button type="button" :class="['chip', { active: !trust }]" @click="setTrust('')">全部</button>
            <button type="button" :class="['chip', { active: trust === 'official' }]" @click="setTrust('official')">官方</button>
            <button type="button" :class="['chip', { active: trust === 'verified' }]" @click="setTrust('verified')">认证</button>
            <button type="button" :class="['chip', { active: trust === 'community' }]" @click="setTrust('community')">社区</button>
          </div>
        </div>
        <div class="browse-toolbar-right">
          <div class="chip-group">
            <button type="button" :class="['chip', { active: view === 'grid' }]" @click="pushFilters({ view: 'grid' })" aria-label="网格视图">网格</button>
            <button type="button" :class="['chip', { active: view === 'list' }]" @click="pushFilters({ view: 'list' })" aria-label="列表视图">列表</button>
          </div>
          <button v-if="hasFilters" type="button" class="btn btn-ghost btn-sm" @click="resetFilters">清除筛选</button>
        </div>
      </div>

      <div v-if="loading" class="grid">
        <div v-for="i in 9" :key="i" class="card skeleton" style="height: 220px"></div>
      </div>
      <div v-else-if="plugins.length" :class="['grid', { 'list-view': view === 'list' }]">
        <PluginCard v-for="p in plugins" :key="p.plugin_id" :plugin="p" />
      </div>
      <EmptyState v-else title="暂无匹配插件" message="试试更换筛选条件、关键字或者回到推荐页找找。" />

      <nav v-if="!loading && totalPages > 1" class="pagination">
        <button type="button" class="page-btn" :disabled="page <= 1" @click="setPage(page - 1)">上一页</button>
        <template v-for="pn in pageRange" :key="pn">
          <span v-if="pn === -1" class="page-ellipsis">…</span>
          <button v-else type="button" :class="['page-btn', { active: pn === page }]" @click="setPage(pn)">{{ pn }}</button>
        </template>
        <button type="button" class="page-btn" :disabled="page >= totalPages" @click="setPage(page + 1)">下一页</button>
      </nav>
    </main>
  </div>
</template>

<style scoped>
.browse-page {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: var(--space-7);
  width: min(var(--shell-max), 100%);
  margin: 0 auto;
  padding: var(--space-6) var(--space-7) var(--space-16);
  align-items: flex-start;
}

@media (max-width: 1023px) {
  .browse-page { grid-template-columns: 1fr; padding: var(--space-5) var(--space-4) var(--space-12); }
}

.browse-side {
  position: sticky;
  top: calc(var(--topbar-h) + var(--kicker-h) + var(--space-5));
  align-self: flex-start;
  display: grid; gap: var(--space-5);
  padding: var(--space-5);
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  max-height: calc(100vh - var(--topbar-h) - var(--kicker-h) - var(--space-7));
  overflow-y: auto;
  scrollbar-width: thin;
  animation: fade-up var(--dur-slow) var(--ease-emphasized) both;
}
@media (max-width: 1023px) {
  .browse-side { position: static; max-height: none; }
}

.browse-side-section { display: grid; gap: 6px; }
.browse-side-section + .browse-side-section {
  padding-top: var(--space-4);
  border-top: 1px dashed var(--line);
}
.browse-side-section h4 {
  margin: 0 0 4px;
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 11px; color: var(--ink-500);
  text-transform: uppercase;
}
.browse-side-section ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 1px; }
.browse-side-section li button {
  width: 100%; text-align: left;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--ink-700);
  position: relative;
  transition: background var(--dur-fast), color var(--dur-fast);
}
.browse-side-section li button:hover { background: var(--surface-hover); color: var(--ink-900); }
.browse-side-section li button.active {
  background: var(--blue-100); color: var(--blue-700); font-weight: 700;
  padding-left: 14px;
}
.browse-side-section li button.active::before {
  content: ""; position: absolute;
  left: 0; top: 50%; transform: translateY(-50%);
  width: 3px; height: 16px; border-radius: 2px;
  background: var(--blue-500);
}

.browse-main {
  min-width: 0;
  display: grid; gap: var(--space-4);
  animation: fade-up var(--dur-slow) var(--ease-emphasized) both;
}

.browse-crumb {
  display: flex; align-items: center; gap: 8px;
  font-family: var(--font-mono); font-size: 11.5px;
  color: var(--ink-500); letter-spacing: 0.04em;
}
.browse-crumb-link { color: var(--blue-700); font-weight: 700; }
.browse-crumb-sep  { color: var(--ink-300); }
.browse-crumb-text { color: var(--ink-500); }
.browse-crumb-active { color: var(--ink-900); }

.browse-head {
  display: flex; justify-content: space-between; align-items: flex-end; gap: var(--space-4);
  flex-wrap: wrap;
}
.browse-head-titles h1 {
  margin: 0;
  font-family: var(--font-display); font-weight: 900;
  font-size: clamp(28px, 3vw, 36px);
  line-height: 1.1;
  color: var(--ink-900);
}
.browse-head-titles p {
  margin: 4px 0 0;
  color: var(--ink-500); font-size: 13.5px;
}
.browse-head-count {
  display: flex; align-items: baseline; gap: 6px;
}
.browse-head-count strong {
  font-family: var(--font-brand);
  letter-spacing: 0.04em;
  font-size: 36px;
  color: var(--ink-900);
  line-height: 1;
}
.browse-head-count small {
  font-family: var(--font-mono); font-size: 11px;
  color: var(--ink-500); letter-spacing: 0.06em;
}

.browse-toolbar {
  display: flex; justify-content: space-between; align-items: center; gap: var(--space-3);
  flex-wrap: wrap;
  padding: 10px 12px;
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
}
.browse-toolbar-left, .browse-toolbar-right {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
.browse-toolbar select {
  padding: 6px 12px;
  border: 1.5px solid var(--line); border-radius: var(--radius-sm);
  background: var(--surface);
  font-size: 13px; color: var(--ink-900);
}
.browse-toolbar select:focus { outline: none; border-color: var(--blue-500); box-shadow: var(--ring); }

@keyframes fade-up {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  .browse-side, .browse-main { animation: none; }
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
  padding: var(--space-6) 0 var(--space-4);
}
.page-btn {
  min-width: 36px;
  padding: 6px 12px;
  border: 1.5px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--surface);
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-700);
  cursor: pointer;
  transition: background var(--dur-fast), color var(--dur-fast), border-color var(--dur-fast);
}
.page-btn:hover:not(:disabled):not(.active) {
  background: var(--surface-hover);
  border-color: var(--ink-300);
  color: var(--ink-900);
}
.page-btn.active {
  background: var(--blue-600, #2563eb);
  border-color: var(--blue-600, #2563eb);
  color: #fff;
  cursor: default;
}
.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.page-ellipsis {
  padding: 0 4px;
  font-size: 14px;
  color: var(--ink-400);
  user-select: none;
}
</style>
