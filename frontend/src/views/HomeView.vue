<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useHomeStore } from '@/stores/home'
import { useTaxonomyStore } from '@/stores/taxonomy'
import { formatNumber } from '@/utils/format'
import type { CurationEntry, Plugin } from '@/types'
import HeroPoster from '@/components/HeroPoster.vue'
import AuthorReel from '@/components/AuthorReel.vue'
import LatestStrip from '@/components/LatestStrip.vue'
import CategoryQuickJump from '@/components/CategoryQuickJump.vue'
import VolKickerBar from '@/components/VolKickerBar.vue'
import PluginCard from '@/components/PluginCard.vue'
import api from '@/api'

const home = useHomeStore()
const taxonomy = useTaxonomyStore()
const router = useRouter()

const heroSlides = computed<CurationEntry[]>(() => {
  const showcase = home.showcase || []
  return showcase.length ? showcase : []
})

const heroFromFeatured = computed<CurationEntry[]>(() => {
  if (heroSlides.value.length) return heroSlides.value
  const fromFeatured = home.featuredPlugins.slice(0, 5)
  if (!fromFeatured.length) return []
  return fromFeatured.map((plugin, idx) => ({
    id: -1 - idx,
    slot_type: 'featured_plugin',
    target_type: 'plugin',
    target_id: plugin.plugin_id,
    sort_order: idx,
    enabled: true,
    audience: 'all',
    display_meta: {},
    plugin,
    author: null,
    signature_plugin: null,
    starts_at: null,
    ends_at: null,
    signature_plugin_id: null,
    created_by: 'fallback',
    created_at: plugin.updated_at,
    updated_at: plugin.updated_at,
  } satisfies CurationEntry))
})

const reelCurated = computed<CurationEntry[]>(() =>
  (home.showcase || []).filter((entry) => entry.target_type === 'author').slice(0, 12),
)
const trendingAuthors = computed(() => home.trendingAuthors)

const latestPlugins = computed<Plugin[]>(() => home.data?.latest || [])
const topRated = computed<Plugin[]>(() => home.data?.top_rated || [])
const categoriesPreview = computed<Record<string, Plugin[]>>(() => home.data?.categories_preview || {})

const stats = computed(() => home.data?.stats)

const popularSkills = ref<Skill[]>([])

function gotoBrowse(query?: Record<string, string>): void {
  void router.push({ name: 'market', query: query || {} })
}

function freshCount(): number {
  const items = latestPlugins.value
  if (!items.length) return 0
  const week = Date.now() - 7 * 24 * 3600 * 1000
  return items.filter((p) => new Date(p.created_at || p.updated_at).getTime() > week).length
}

onMounted(async () => {
  await taxonomy.load()
  await home.loadHome()
  try {
    const res = await api.skills.list({ sort: 'downloads', page_size: 3 })
    popularSkills.value = res.items || []
  } catch (e) {
    // skip on error
  }
})
</script>

<template>
  <VolKickerBar :count="freshCount()" />

  <div class="home-view">

    <!-- HERO -->
    <section class="home-hero" data-anim="enter-1">
      <div class="home-hero-headline">
        <span class="kicker">Vol &middot; 本期市集</span>
        <h1>
          本期 <span class="hl">市集</span>
        </h1>
        <p>
          这里是运营手挑的精选插件 + 代表作者，每期更新一次。想直接看完所有插件？
          <a class="link-inline" @click.prevent="gotoBrowse()" href="#">前往浏览页 →</a>
        </p>
      </div>

      <div class="home-hero-grid">
        <HeroPoster :items="heroFromFeatured" />

        <aside class="home-hero-side">
          <div class="home-hero-meta-card">
            <div class="blob" aria-hidden="true"></div>
            <span class="kicker-mini">MARKET DATA</span>
            <div class="home-hero-meta-stats" v-if="stats">
              <div>
                <b>{{ formatNumber(stats.published_plugins ?? stats.plugins_total ?? 0) }}</b>
                <span>已发布</span>
              </div>
              <div>
                <b>{{ formatNumber(stats.authors_total ?? 0) }}</b>
                <span>作者</span>
              </div>
              <div>
                <b>{{ formatNumber(stats.versions_total ?? 0) }}</b>
                <span>版本</span>
              </div>
            </div>
            <div class="home-hero-meta-stats" v-else>
              <div><b class="skeleton" style="height: 24px; width: 36px"></b><span>已发布</span></div>
              <div><b class="skeleton" style="height: 24px; width: 36px"></b><span>作者</span></div>
              <div><b class="skeleton" style="height: 24px; width: 36px"></b><span>版本</span></div>
            </div>
            <a class="home-hero-meta-cta" @click.prevent="gotoBrowse()" href="#">浏览全部插件 →</a>
          </div>

          <div class="home-hero-shortcut">
            <span class="kicker-mini">QUICK JUMP</span>
            <p class="shortcut-tip">想直接定位？跳到浏览页对应入口。</p>
            <div class="shortcut-grid">
              <button type="button" class="shortcut-tile" @click="gotoBrowse({ sort: 'updated' })">
                <span class="t-num">↻</span>
                <span class="t-text">最近更新</span>
              </button>
              <button type="button" class="shortcut-tile" @click="gotoBrowse({ sort: 'rating' })">
                <span class="t-num">★</span>
                <span class="t-text">高分好评</span>
              </button>
              <button type="button" class="shortcut-tile" @click="gotoBrowse({ sort: 'trending' })">
                <span class="t-num">↑</span>
                <span class="t-text">趋势上升</span>
              </button>
              <button type="button" class="shortcut-tile" @click="gotoBrowse({ sort: 'downloads' })">
                <span class="t-num">↓</span>
                <span class="t-text">下载最多</span>
              </button>
              <button type="button" class="shortcut-tile" @click="gotoBrowse({ trust_level: 'official' })">
                <span class="t-num">公</span>
                <span class="t-text">官方插件</span>
              </button>
              <button type="button" class="shortcut-tile" @click="gotoBrowse({ trust_level: 'verified' })">
                <span class="t-num">认</span>
                <span class="t-text">认证作者</span>
              </button>
              <button type="button" class="shortcut-tile" @click="router.push({ name: 'skills' })">
                <span class="t-num">⚡</span>
                <span class="t-text">Skill 市场</span>
              </button>
            </div>
          </div>
        </aside>
      </div>
    </section>

    <!-- FEATURED AUTHORS -->
    <section class="section" v-if="reelCurated.length || trendingAuthors.length" data-anim="enter-2">
      <div class="section-head">
        <div class="titles">
          <span class="kicker">FEATURED AUTHORS · 本期作者</span>
          <h2>精选作者</h2>
          <p>每位作者带一件代表作。在区域内滚动鼠标即可翻页。</p>
        </div>
      </div>
      <AuthorReel :curated="reelCurated" :trending="trendingAuthors" />
    </section>

    <!-- LATEST STRIP -->
    <section class="section" v-if="latestPlugins.length" data-anim="enter-3">
      <div class="section-head">
        <div class="titles">
          <span class="kicker">LATEST · 最近更新</span>
          <h2>近期上新</h2>
          <p>过去 7 天内新发布或新版本的插件。</p>
        </div>
        <div class="actions">
          <button type="button" class="btn btn-ghost" @click="gotoBrowse({ sort: 'updated' })">看全部更新 →</button>
        </div>
      </div>
      <LatestStrip :items="latestPlugins" />
    </section>

    <!-- TOP RATED -->
    <section class="section" v-if="topRated.length" data-anim="enter-4">
      <div class="section-head">
        <div class="titles">
          <span class="kicker">TOP RATED · 高分推荐</span>
          <h2>高分好评</h2>
          <p>用户口碑最稳的插件。</p>
        </div>
        <div class="actions">
          <button type="button" class="btn btn-ghost" @click="gotoBrowse({ sort: 'rating' })">看完整榜单 →</button>
        </div>
      </div>
      <div class="grid">
        <PluginCard v-for="plugin in topRated.slice(0, 6)" :key="plugin.plugin_id" :plugin="plugin" />
      </div>
    </section>

    <!-- POPULAR SKILLS -->
    <section class="section" v-if="popularSkills.length" data-anim="enter-5">
      <div class="section-head">
        <div class="titles">
          <span class="kicker">POPULAR SKILLS · 热门技能</span>
          <h2>Skill 推荐</h2>
          <p>增强 MoFox 的独立技能模块。</p>
        </div>
        <div class="actions">
          <button type="button" class="btn btn-ghost" @click="router.push({ name: 'skills' })">去 Skill 市场 →</button>
        </div>
      </div>
      <div class="skills-grid">
        <article
          v-for="skill in popularSkills"
          :key="skill.skill_id"
          class="skill-card"
          @click="router.push({ name: 'skill', params: { id: skill.skill_id } })"
        >
          <div class="skill-card-icon">
            <img v-if="skill.icon_url" :src="skill.icon_url" :alt="skill.display_name">
            <span v-else>{{ skill.display_name[0]?.toUpperCase() || '?' }}</span>
          </div>
          <div class="skill-card-body">
            <h3>{{ skill.display_name }}</h3>
            <p class="skill-card-desc">{{ skill.description.length > 80 ? skill.description.slice(0, 80) + '…' : skill.description }}</p>
            <div class="skill-card-meta">
              <span class="skill-card-author">{{ skill.owner_display_name || skill.owner_login || skill.owner_id }}</span>
              <span class="skill-card-stat">⭐ {{ skill.rating_avg?.toFixed(1) || '-' }}</span>
              <span class="skill-card-stat">⬇ {{ skill.download_count }}</span>
            </div>
          </div>
        </article>
      </div>
    </section>

    <!-- CATEGORY -->
    <section class="section" v-if="Object.keys(categoriesPreview).length" data-anim="enter-5">
      <div class="section-head">
        <div class="titles">
          <span class="kicker">CATEGORIES · 分类速通</span>
          <h2>挑个分区逛</h2>
          <p>跳到浏览页对应分类。</p>
        </div>
      </div>
      <CategoryQuickJump :preview="categoriesPreview" />
    </section>

    <!-- BIG STATS -->
    <div class="home-stat-strip" v-if="stats" data-anim="enter-6">
      <div>
        <div class="v">{{ formatNumber(stats.published_plugins ?? stats.plugins_total ?? 0) }}</div>
        <div class="l">已发布插件</div>
      </div>
      <div>
        <div class="v">{{ formatNumber(stats.authors_total ?? 0) }}</div>
        <div class="l">在册作者</div>
      </div>
      <div>
        <div class="v">{{ formatNumber(stats.versions_total ?? 0) }}</div>
        <div class="l">总版本数</div>
      </div>
      <div>
        <div class="v">{{ formatNumber(stats.downloads_total ?? 0) }}</div>
        <div class="l">累计安装</div>
      </div>
    </div>

  </div>
</template>

<style scoped>
.home-view {
  width: min(var(--shell-max), 100%);
  margin: 0 auto;
  padding: var(--space-7) var(--space-7) var(--space-16);
}
@media (max-width: 768px) {
  .home-view { padding: var(--space-5) var(--space-4) var(--space-12); }
}

.home-hero {
  display: flex; flex-direction: column;
  gap: var(--space-6);
  margin-bottom: var(--space-12);
}

.home-hero-headline { display: grid; gap: 6px; }
.home-hero-headline .kicker {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 12px; color: var(--blue-700);
}
.home-hero-headline .kicker::before { content: ""; width: 22px; height: 2px; background: var(--coral); }
.home-hero-headline h1 {
  margin: 0;
  font-family: var(--font-display); font-weight: 900;
  font-size: clamp(40px, 5.6vw, 64px);
  line-height: 1.02;
  letter-spacing: var(--letter-tight);
  color: var(--ink-900);
}
.home-hero-headline h1 .hl {
  position: relative;
  color: var(--blue-700);
  background: linear-gradient(180deg, transparent 60%, var(--lemon) 60%, var(--lemon) 92%, transparent 92%);
  padding: 0 0.08em;
  display: inline;
}
.home-hero-headline p {
  margin: 8px 0 0;
  color: var(--ink-500);
  font-size: var(--fs-lg);
  max-width: 60ch;
}
.link-inline {
  color: var(--blue-700); font-weight: 700;
  border-bottom: 2px solid var(--coral);
  padding-bottom: 1px;
}

.home-hero-grid {
  display: grid;
  grid-template-columns: 1.45fr 1fr;
  gap: var(--space-5);
  align-items: stretch;
}
@media (max-width: 980px) {
  .home-hero-grid { grid-template-columns: 1fr; }
}

.home-hero-side {
  display: grid; gap: var(--space-3);
  align-content: stretch;
  min-width: 0;
}

/* MARKET DATA card with corner blob — peek-on-hover */
.home-hero-meta-card {
  position: relative; overflow: hidden;
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  padding: var(--space-5);
  display: grid; gap: var(--space-3);
  isolation: isolate;
  transition: border-color var(--dur-base);
}
.home-hero-meta-card:hover { border-color: var(--blue-300); }
.home-hero-meta-card .blob {
  position: absolute;
  top: -50px;            /* 默认露出一部分藏在右上 */
  right: -60px;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--lemon) 0%, #ffe9a8 70%, transparent 100%);
  opacity: 0.78;
  pointer-events: none;
  z-index: 0;
  transition: top var(--dur-slow) var(--ease-emphasized),
              right var(--dur-slow) var(--ease-emphasized),
              opacity var(--dur-slow);
}
.home-hero-meta-card:hover .blob {
  /* 鼠标进入时，球往里滑动一小段 */
  top: -28px;
  right: -38px;
  opacity: 0.95;
}
.home-hero-meta-card > *:not(.blob) { position: relative; z-index: 1; }

.kicker-mini {
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 11px; color: var(--ink-500); text-transform: uppercase;
}

.home-hero-meta-stats {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
}
.home-hero-meta-stats > div { display: grid; gap: 2px; }
.home-hero-meta-stats b {
  font-family: var(--font-brand); letter-spacing: var(--letter-bebas);
  font-size: 28px; color: var(--ink-900); line-height: 1;
}
.home-hero-meta-stats span {
  font-family: var(--font-mono);
  font-size: 11px; color: var(--ink-500);
  letter-spacing: 0.04em;
}

.home-hero-meta-cta {
  font-family: var(--font-mono); font-weight: 600;
  font-size: 12.5px; color: var(--blue-700);
  border-bottom: 2px solid var(--coral);
  padding-bottom: 1px;
  align-self: flex-start;
  transition: color var(--dur-fast);
}
.home-hero-meta-cta:hover { color: var(--ink-900); }

/* QUICK JUMP — 6 tile grid */
.home-hero-shortcut {
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  display: grid; gap: var(--space-3);
}
.shortcut-tip {
  margin: 0;
  font-size: 12.5px; color: var(--ink-500); line-height: 1.5;
}
.shortcut-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.shortcut-tile {
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px;
  padding: 12px 8px;
  border-radius: var(--radius-md);
  background: var(--surface-soft);
  border: 1.5px solid transparent;
  color: var(--ink-700);
  transition: transform var(--dur-fast) var(--ease-pop),
              background var(--dur-fast),
              border-color var(--dur-fast),
              box-shadow var(--dur-fast),
              color var(--dur-fast);
}
.shortcut-tile:hover {
  border-color: var(--ink-900);
  background: var(--surface);
  transform: translate(-1px, -1px);
  box-shadow: var(--shadow-poster-soft);
  color: var(--ink-900);
}
.shortcut-tile .t-num {
  font-family: var(--font-display); font-weight: 900;
  font-size: 24px; color: var(--blue-700); line-height: 1;
}
.shortcut-tile .t-text { font-size: 12px; font-weight: 600; }

@media (max-width: 480px) {
  .shortcut-grid { grid-template-columns: repeat(2, 1fr); }
}

.home-stat-strip {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 0;
  border-top: 2px solid var(--ink-900);
  border-bottom: 2px solid var(--ink-900);
  padding: var(--space-4) 0;
  margin-top: var(--space-12);
}
.home-stat-strip > div {
  padding: 0 var(--space-6);
  border-right: 1px dashed var(--line);
  display: grid; align-content: center;
}
.home-stat-strip > div:last-child { border-right: none; }
.home-stat-strip .v {
  font-family: var(--font-brand); letter-spacing: 0.04em;
  font-size: 44px; line-height: 0.95; color: var(--ink-900);
}
.home-stat-strip .l {
  font-family: var(--font-mono); font-size: 11px;
  letter-spacing: 0.08em; color: var(--ink-500);
  text-transform: uppercase;
  margin-top: 8px;
}

@media (max-width: 768px) {
  .home-hero-headline h1 { font-size: 36px; }
  .home-hero { gap: var(--space-4); margin-bottom: var(--space-7); }
  .home-stat-strip { grid-template-columns: repeat(2, 1fr); gap: var(--space-3); padding: var(--space-3) 0; }
  .home-stat-strip > div { padding: 0 var(--space-4); border-right: none; }
  .home-stat-strip .v { font-size: 30px; }
  .home-hero-meta-stats { grid-template-columns: 1fr 1fr 1fr; }
  .home-hero-meta-stats b { font-size: 22px; }
  .shortcut-grid { grid-template-columns: repeat(3, 1fr); }
  .shortcut-tile { padding: 10px 6px; }
  .shortcut-tile .t-num { font-size: 20px; }
  .shortcut-tile .t-text { font-size: 11px; }
}
@media (max-width: 480px) {
  .home-hero-headline h1 { font-size: 30px; }
  .shortcut-grid { grid-template-columns: repeat(2, 1fr); }
}

/* === entry animations === */
[data-anim] {
  animation: fade-up var(--dur-slow) var(--ease-emphasized) both;
}
[data-anim="enter-1"] { animation-delay: 60ms; }
[data-anim="enter-2"] { animation-delay: 160ms; }
[data-anim="enter-3"] { animation-delay: 220ms; }
[data-anim="enter-4"] { animation-delay: 280ms; }
[data-anim="enter-5"] { animation-delay: 340ms; }
[data-anim="enter-6"] { animation-delay: 400ms; }
@keyframes fade-up {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  [data-anim] { animation: none; }
}

/* Skills grid */
.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-4);
}
.skill-card {
  display: grid; grid-template-columns: auto 1fr; gap: var(--space-3);
  padding: var(--space-4);
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--dur-fast);
}
.skill-card:hover {
  border-color: var(--blue-300);
  box-shadow: var(--shadow-card);
  transform: translateY(-2px);
}
.skill-card-icon {
  width: 48px; height: 48px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--coral), var(--lemon));
  display: grid; place-items: center;
  font-family: var(--font-display); font-weight: 800; font-size: 20px;
  color: var(--ink-900);
  overflow: hidden;
  flex-shrink: 0;
}
.skill-card-icon img { width: 100%; height: 100%; object-fit: cover; }
.skill-card-body { display: grid; gap: 4px; min-width: 0; }
.skill-card-body h3 {
  margin: 0;
  font-family: var(--font-display); font-weight: 800;
  font-size: 16px; line-height: 1.2;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.skill-card-desc {
  margin: 0;
  font-size: 13px; color: var(--ink-600);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.5;
}
.skill-card-meta {
  display: flex; gap: 12px; flex-wrap: wrap;
  font-family: var(--font-mono); font-size: 11.5px; color: var(--ink-500);
  margin-top: 4px;
}
.skill-card-author { font-weight: 600; }
.skill-card-stat { opacity: 0.8; }
</style>
