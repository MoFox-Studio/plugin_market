<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api'
import { useTaxonomyStore } from '@/stores/taxonomy'
import { formatNumber, categoryLabel } from '@/utils/format'
import type { Plugin, MarketStats, FeaturedData } from '@/types'
import PluginCard from '@/components/PluginCard.vue'
import EmptyState from '@/components/EmptyState.vue'

const route = useRoute()
const taxonomy = useTaxonomyStore()

// Filter state
const sort = ref('updated')
const category = ref('')
const tag = ref('')
const trust = ref('')
const view = ref('grid')
const query = ref('')

// Data
const plugins = ref<Plugin[]>([])
const total = ref(0)
const stats = ref<MarketStats | null>(null)
const featured = ref<FeaturedData | null>(null)
const loading = ref(true)

const hasFilters = computed(() => !!(query.value || category.value || tag.value || trust.value))
const showFeatured = computed(() => !hasFilters.value && sort.value === 'updated')

const filterSummary = computed(() => {
  const parts: string[] = []
  if (query.value) parts.push(`关键字 "${query.value}"`)
  if (category.value) parts.push(`分类 ${categoryLabel(category.value)}`)
  if (tag.value) parts.push(`标签 #${tag.value}`)
  if (trust.value) parts.push(`${trust.value} 插件`)
  return parts.length ? `当前筛选：${parts.join(' · ')}` : '浏览所有已发布的插件，支持标签、分类和信任等级筛选。'
})

async function loadPlugins() {
  loading.value = true
  const p = new URLSearchParams()
  p.set('limit', '24')
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

async function loadStats() {
  stats.value = await api.get<MarketStats>('/api/v1/market/stats').catch(() => null)
}

async function loadFeatured() {
  featured.value = await api.get<FeaturedData>('/api/v1/market/featured?limit=6').catch(() => null)
}

function setCategory(cat: string) {
  category.value = cat
  loadPlugins()
}

function setTag(t: string) {
  tag.value = t
  loadPlugins()
}

function setTrust(t: string) {
  trust.value = t
  loadPlugins()
}

function setSort(s: string) {
  sort.value = s
  loadPlugins()
}

function resetFilters() {
  query.value = ''
  category.value = ''
  tag.value = ''
  trust.value = ''
  sort.value = 'updated'
  loadPlugins()
}

function handleNavClick(navKey: string) {
  if (navKey === 'all') {
    resetFilters()
  } else {
    resetFilters()
  }
}

watch(() => route.query.q, (q) => {
  if (q !== undefined) {
    query.value = (q as string) || ''
    loadPlugins()
  }
})

onMounted(async () => {
  if (route.query.q) query.value = route.query.q as string
  await taxonomy.load()
  await Promise.all([loadPlugins(), loadStats(), loadFeatured()])
})
</script>

<template>
  <section class="hero">
    <div>
      <h1>Neo-MoFox 插件市场</h1>
      <p>在这里发现、评价并参与共建 Neo-MoFox 插件生态。社区审核 · 真实口碑 · 即装即用。</p>
    </div>
    <div class="hero-stats" v-if="stats">
      <div class="hero-stat"><b>{{ formatNumber(stats.published_plugins || stats.plugins_total || 0) }}</b><span>已发布</span></div>
      <div class="hero-stat"><b>{{ formatNumber(stats.versions_total || 0) }}</b><span>版本</span></div>
      <div class="hero-stat"><b>{{ formatNumber(stats.authors_total || 0) }}</b><span>作者</span></div>
    </div>
    <div class="hero-stats" v-else>
      <div class="hero-stat"><b class="skeleton" style="height:1.4rem;width:48px">&nbsp;</b><span>已发布</span></div>
      <div class="hero-stat"><b class="skeleton" style="height:1.4rem;width:48px">&nbsp;</b><span>版本</span></div>
      <div class="hero-stat"><b class="skeleton" style="height:1.4rem;width:48px">&nbsp;</b><span>作者</span></div>
    </div>
  </section>

  <div class="market-layout">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-section">
        <h4>快速导航</h4>
        <ul class="sidebar-list">
          <li><button type="button" :class="{ active: !hasFilters && sort === 'updated' }" @click="handleNavClick('all')">全部插件</button></li>
          <li><button type="button" @click="sort = 'trending'; loadPlugins()">热门推荐</button></li>
          <li><button type="button" @click="sort = 'rating'; loadPlugins()">高分好评</button></li>
          <li><button type="button" @click="sort = 'updated'; loadPlugins()">最近更新</button></li>
        </ul>
      </div>
      <div class="sidebar-section">
        <h4>分类</h4>
        <ul class="sidebar-list">
          <li><button type="button" :class="{ active: !category }" @click="setCategory('')">全部分类</button></li>
          <li v-for="cat in taxonomy.categories" :key="cat">
            <button type="button" :class="{ active: category === cat }" @click="setCategory(cat)">{{ categoryLabel(cat) }}</button>
          </li>
        </ul>
      </div>
      <div class="sidebar-section">
        <h4>热门标签</h4>
        <ul class="sidebar-list">
          <li><button type="button" :class="{ active: !tag }" @click="setTag('')">全部标签</button></li>
          <li v-for="t in taxonomy.tags.slice(0, 30)" :key="t">
            <button type="button" :class="{ active: tag === t }" @click="setTag(t)">#{{ t }}</button>
          </li>
        </ul>
      </div>
    </aside>

    <!-- Main content -->
    <div class="main-col">
      <!-- Featured sections -->
      <div v-if="showFeatured && featured">
        <section
          v-for="section in [
            { key: 'ranking', title: '🔥 社区热门', desc: '综合点赞、下载与评价的社区热度榜单。' },
            { key: 'top_rated', title: '⭐ 高分好评', desc: '用户评分最高的插件，口碑推荐。' },
            { key: 'latest', title: '上新速递', desc: '近期有新版本发布的插件。' },
          ].filter(s => (featured![s.key] || []).length)"
          :key="section.key"
          class="section"
        >
          <div class="section-head">
            <div><h2>{{ section.title }}</h2><p>{{ section.desc }}</p></div>
          </div>
          <div class="grid">
            <PluginCard v-for="p in featured[section.key]?.slice(0, 6)" :key="p.plugin_id" :plugin="p" />
          </div>
        </section>
      </div>

      <!-- Toolbar -->
      <section class="section">
        <div class="toolbar">
          <div class="toolbar-left">
            <label for="sort-select">排序</label>
            <select id="sort-select" :value="sort" @change="setSort(($event.target as HTMLSelectElement).value)">
              <option value="updated">最近更新</option>
              <option value="popular">综合热度</option>
              <option value="rating">评分优先</option>
              <option value="downloads">下载最多</option>
              <option value="likes">点赞最多</option>
              <option value="trending">趋势上升</option>
            </select>
            <div class="chip-group">
              <button type="button" :class="['chip', { active: !trust }]" @click="setTrust('')">全部</button>
              <button type="button" :class="['chip', { active: trust === 'official' }]" @click="setTrust('official')">官方</button>
              <button type="button" :class="['chip', { active: trust === 'verified' }]" @click="setTrust('verified')">认证</button>
              <button type="button" :class="['chip', { active: trust === 'community' }]" @click="setTrust('community')">社区</button>
            </div>
          </div>
          <div class="toolbar-right">
            <span style="font-size:0.82rem;color:var(--muted)">共 {{ total }} 个结果</span>
            <div class="chip-group">
              <button type="button" :class="['chip', { active: view === 'grid' }]" @click="view = 'grid'">网格</button>
              <button type="button" :class="['chip', { active: view === 'list' }]" @click="view = 'list'">列表</button>
            </div>
          </div>
        </div>

        <div class="section-head">
          <div>
            <h2>全部插件 <span class="badge trust-community">{{ total }}</span></h2>
            <p>{{ filterSummary }}</p>
          </div>
          <button v-if="hasFilters" type="button" class="btn btn-ghost btn-sm" @click="resetFilters">清除筛选</button>
        </div>

        <!-- Plugin grid -->
        <div v-if="loading" class="grid">
          <div v-for="i in 6" :key="i" class="card skeleton" style="height:180px"></div>
        </div>
        <div v-else-if="plugins.length" :class="['grid', { 'list-view': view === 'list' }]">
          <PluginCard v-for="p in plugins" :key="p.plugin_id" :plugin="p" />
        </div>
        <EmptyState v-else title="暂无匹配插件" message="试试更换筛选条件或关键字。" />
      </section>
    </div>
  </div>
</template>
