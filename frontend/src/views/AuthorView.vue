<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { formatNumber, formatRelative } from '@/utils/format'
import type { AuthorFollowState, AuthorProfile, PinnedPlugin, Plugin } from '@/types'
import PluginCard from '@/components/PluginCard.vue'
import EmptyState from '@/components/EmptyState.vue'

const props = defineProps({ id: { type: String, required: true } })
const auth = useAuthStore()
const toast = useToastStore()
const route = useRoute()
const router = useRouter()

const plugins = ref<Plugin[]>([])
const author = ref<Plugin | null>(null)
const profile = ref<AuthorProfile | null>(null)
const pins = ref<PinnedPlugin[]>([])
const followState = ref<AuthorFollowState | null>(null)
const followPending = ref(false)
const loading = ref(true)
const page = ref(1)
const total = ref(0)
const pageSize = 21
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const heroStyle = computed(() => {
  if (profile.value?.background_image_url) {
    return {
      backgroundImage: `linear-gradient(135deg, rgba(11, 18, 32, 0.74) 0%, rgba(11, 18, 32, 0.32) 60%, rgba(11, 18, 32, 0.6) 100%), url(${profile.value.background_image_url})`,
      backgroundSize: 'cover',
      backgroundPosition: 'center',
    }
  }
  return {}
})

const totals = computed(() => {
  const items = plugins.value
  return {
    plugins: total.value,
    likes: items.reduce((acc, p) => acc + (p.likes_count || 0), 0),
    downloads: items.reduce((acc, p) => acc + (p.downloads_count || 0), 0),
  }
})

const pinnedPlugins = computed(() => pins.value.filter((item) => item.plugin))
const isOwnPage = computed(() => auth.viewer?.author_id === props.id)

const displayName = computed(() =>
  author.value?.owner_display_name ||
  author.value?.owner_login ||
  profile.value?.author_id ||
  props.id,
)
const githubLogin = computed(() => author.value?.owner_login || props.id)

async function loadPage() {
  loading.value = true
  try {
    const [result, profileResult, pinResult, followResult] = await Promise.all([
      api.get(`/api/v1/plugins?limit=${pageSize}&offset=${(page.value - 1) * pageSize}&sort=popular&author_id=${encodeURIComponent(props.id)}`),
      api.get(`/api/v1/authors/${encodeURIComponent(props.id)}/profile`).catch(() => null),
      api.get(`/api/v1/authors/${encodeURIComponent(props.id)}/pins`).catch(() => []),
      api.authors.followState(props.id).catch(() => null),
    ])
    const items = result.items || []
    plugins.value = items
    total.value = result.total || 0
    author.value = items.find((p: Plugin) => p.owner_id === props.id) || items[0] || null
    profile.value = profileResult
    pins.value = pinResult
    followState.value = followResult
  } catch {
    plugins.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function setPage(nextPage: number) {
  const bounded = Math.min(Math.max(1, nextPage), totalPages.value)
  void router.push({ query: { ...route.query, page: bounded === 1 ? undefined : String(bounded) } })
}

async function toggleFollow() {
  if (!auth.isAuthenticated) {
    toast.show('请先登录', '')
    setTimeout(() => { location.href = auth.getLoginUrl(`/author/${encodeURIComponent(props.id)}`) }, 600)
    return
  }
  followPending.value = true
  try {
    followState.value = await api.authors.toggleFollow(props.id)
    toast.show(followState.value.following ? '已关注作者' : '已取消关注', 'ok')
  } catch (e) {
    toast.show((e as Error).message || '操作失败', 'error')
  } finally {
    followPending.value = false
  }
}

watch(
  () => [props.id, route.query.page],
  () => {
    page.value = Math.max(1, Number.parseInt(String(route.query.page || '1'), 10) || 1)
    void loadPage()
  },
  { immediate: true },
)
</script>

<template>
  <div class="author-page">
    <div class="author-loading" v-if="loading">加载中…</div>

    <template v-else>
      <header
        class="author-hero"
        :class="{ 'has-bg': profile?.background_image_url }"
        :style="heroStyle"
        data-anim="enter-1"
      >
        <div class="author-hero-overlay" v-if="!profile?.background_image_url" aria-hidden="true"></div>
        <div class="author-hero-inner shell">
          <div class="author-hero-text">
            <span class="kicker">AUTHOR SPACE</span>
            <h1>{{ displayName }}</h1>
            <p class="author-hero-login">@{{ githubLogin }}</p>
            <p class="author-hero-bio" v-if="profile?.bio">{{ profile.bio }}</p>
            <p class="author-hero-bio is-empty" v-else>这位作者还没有填写公开 Bio，先看看 ta 公开发布的作品吧。</p>

            <div class="author-hero-actions" v-if="!isOwnPage">
              <button type="button" class="btn btn-sm" :disabled="followPending" @click="toggleFollow">
                {{ followState?.following ? '已关注' : '关注作者' }}
              </button>
              <span class="author-followers">{{ formatNumber(followState?.followers_count || 0) }} 位关注者</span>
            </div>

            <div class="author-hero-stats">
              <div><b>{{ formatNumber(totals.plugins) }}</b><span>插件</span></div>
              <div><b>{{ formatNumber(totals.likes) }}</b><span>累计订阅</span></div>
              <div><b>{{ formatNumber(totals.downloads) }}</b><span>累计下载</span></div>
            </div>
          </div>

          <div class="author-hero-avatar-shell">
            <div class="author-hero-avatar" :class="{ 'is-fallback': !author?.owner_avatar_url }">
              <img v-if="author?.owner_avatar_url" :src="author.owner_avatar_url" :alt="displayName">
              <span v-else>{{ displayName[0]?.toUpperCase() || 'A' }}</span>
            </div>
          </div>
        </div>
      </header>

      <div class="shell author-body">

        <section class="author-section" v-if="pinnedPlugins.length" data-anim="enter-2">
          <div class="author-section-head">
            <span class="kicker">PINNED · 置顶作品</span>
            <h2>作者本人推荐</h2>
            <p>下面这些是 ta 自己挑出来想让你先看到的作品。</p>
          </div>
          <div class="pinned-grid">
            <article v-for="pin in pinnedPlugins" :key="pin.plugin_id" class="pinned-cell">
              <div class="pinned-tag" v-if="pin.pinned_reason">
                <span class="pinned-tag-kicker">PIN</span>
                <p>{{ pin.pinned_reason }}</p>
              </div>
              <div class="pinned-tag is-default" v-else>
                <span class="pinned-tag-kicker">PIN</span>
                <p>作者置顶推荐</p>
              </div>
              <PluginCard :plugin="pin.plugin!" />
              <small class="pinned-when">置顶于 {{ formatRelative(pin.pinned_at) }}</small>
            </article>
          </div>
        </section>

        <section class="author-section" data-anim="enter-3">
          <div class="author-section-head">
            <span class="kicker">PUBLISHED · 公开发布</span>
            <h2>{{ pinnedPlugins.length ? '其他公开插件' : '公开插件' }}</h2>
            <p>按综合热度排序。</p>
          </div>
          <div v-if="plugins.length" class="grid">
            <PluginCard v-for="p in plugins" :key="p.plugin_id" :plugin="p" />
          </div>
          <EmptyState v-else title="暂无插件" message="该作者尚未发布任何已审核通过的插件。" />
          <nav v-if="totalPages > 1" class="author-pagination" aria-label="作者插件分页">
            <button type="button" class="btn btn-ghost btn-sm" :disabled="page <= 1" @click="setPage(page - 1)">上一页</button>
            <span>第 {{ page }} / {{ totalPages }} 页 · 共 {{ total }} 个插件</span>
            <button type="button" class="btn btn-ghost btn-sm" :disabled="page >= totalPages" @click="setPage(page + 1)">下一页</button>
          </nav>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.author-page { display: grid; }

.author-loading {
  text-align: center;
  padding: var(--space-16) var(--space-5);
  color: var(--ink-500);
  font-family: var(--font-mono); font-size: 13px;
}

/* === HERO === */
.author-hero {
  position: relative;
  overflow: hidden;
  /* 默认渐变（无背景图时） — 蓝调天空系，柔和不抢戏 */
  background:
    linear-gradient(135deg,
      var(--blue-700) 0%,
      var(--blue-500) 38%,
      #5fb8ff 70%,
      #b9e1fb 110%);
  color: #fff;
  padding-block: var(--space-10);
}
.author-hero.has-bg { background: var(--ink-900); }
.author-hero-overlay {
  position: absolute; inset: 0;
  background:
    radial-gradient(circle at 20% 30%, rgba(255, 255, 255, 0.18) 0%, transparent 60%),
    radial-gradient(circle at 80% 90%, rgba(11, 18, 32, 0.28) 0%, transparent 55%);
  mix-blend-mode: overlay;
  pointer-events: none;
}

.author-hero-inner {
  position: relative; z-index: 1;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--space-6);
  align-items: center;
}
@media (max-width: 768px) {
  .author-hero-inner { grid-template-columns: 1fr; text-align: left; }
}

.author-hero-text { color: #fff; min-width: 0; }
.author-hero-text .kicker {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 12px; color: rgba(255,255,255,0.92);
}
.author-hero-text .kicker::before { content: ""; width: 22px; height: 2px; background: #fff; }
.author-hero-text h1 {
  margin: 8px 0 4px;
  font-family: var(--font-display); font-weight: 900;
  font-size: clamp(36px, 5vw, 56px);
  line-height: 1.05;
  text-shadow: 0 2px 14px rgba(11, 18, 32, 0.34);
}
.author-hero-login {
  margin: 0 0 var(--space-3);
  font-family: var(--font-mono); font-size: 14px;
  color: rgba(255,255,255,0.86);
}
.author-hero-bio {
  margin: 0 0 var(--space-4);
  font-size: 15px; line-height: 1.7;
  max-width: 60ch;
  color: rgba(255,255,255,0.94);
}
.author-hero-bio.is-empty { color: rgba(255,255,255,0.7); font-style: italic; }

.author-hero-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  margin: 0 0 var(--space-4);
  flex-wrap: wrap;
}

.author-followers {
  font-family: var(--font-mono);
  font-size: 12px;
  color: rgba(255,255,255,0.84);
}

.author-hero-stats {
  display: flex; gap: var(--space-6);
  flex-wrap: wrap;
}
.author-hero-stats > div {
  display: grid; gap: 2px;
}
.author-hero-stats b {
  font-family: var(--font-brand); letter-spacing: 0.04em;
  font-size: 28px; line-height: 1;
}
.author-hero-stats span {
  font-family: var(--font-mono); font-size: 11.5px;
  color: rgba(255,255,255,0.78);
  letter-spacing: 0.04em;
}

.author-hero-avatar-shell {
  display: grid; place-items: center;
}
.author-hero-avatar {
  width: 140px; height: 140px;
  border-radius: 50%;
  background: var(--surface);
  display: grid; place-items: center;
  overflow: hidden;
  border: 4px solid #fff;
  box-shadow: 0 14px 40px rgba(11, 18, 32, 0.32);
}
.author-hero-avatar img { width: 100%; height: 100%; object-fit: cover; }
.author-hero-avatar.is-fallback {
  background: linear-gradient(135deg, var(--blue-500), var(--blue-700));
  color: #fff;
  font-family: var(--font-display); font-weight: 900; font-size: 56px;
}
@media (max-width: 768px) {
  .author-hero-avatar { width: 96px; height: 96px; }
}

/* === BODY === */
.author-body {
  padding: var(--space-7) var(--space-7) var(--space-16);
  display: grid; gap: var(--space-12);
}
@media (max-width: 768px) {
  .author-body { padding: var(--space-5) var(--space-4) var(--space-12); }
}

.author-section { display: grid; gap: var(--space-4); }
.author-pagination {
  display: flex; justify-content: center; align-items: center; gap: var(--space-3);
  flex-wrap: wrap; padding-top: var(--space-4);
}
.author-pagination span { font-family: var(--font-mono); font-size: 12px; color: var(--ink-500); }
.author-section-head .kicker {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 12px; color: var(--blue-700);
}
.author-section-head .kicker::before { content: ""; width: 22px; height: 2px; background: var(--coral); }
.author-section-head h2 {
  margin: 6px 0 4px;
  font-family: var(--font-display); font-weight: 900;
  font-size: clamp(24px, 2.6vw, 32px);
  line-height: 1.15;
}
.author-section-head p { margin: 0; color: var(--ink-500); font-size: 13.5px; max-width: 56ch; }

.pinned-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--space-4);
}

.pinned-cell {
  position: relative;
  display: grid; gap: 8px;
  padding: var(--space-3);
  background: var(--surface);
  border: 1.5px solid var(--blue-200);
  border-radius: var(--radius-md);
}

.pinned-tag {
  display: grid; grid-template-columns: auto 1fr; gap: 8px;
  align-items: flex-start;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: var(--blue-100);
  color: var(--blue-700);
}
.pinned-tag.is-default { background: var(--surface-soft); color: var(--ink-500); }
.pinned-tag-kicker {
  display: grid; place-items: center;
  width: 30px; height: 18px;
  background: var(--coral); color: #fff;
  border-radius: var(--radius-sm);
  font-family: var(--font-brand); letter-spacing: 0.06em;
  font-size: 10px; font-weight: 700;
}
.pinned-tag.is-default .pinned-tag-kicker { background: var(--ink-500); }
.pinned-tag p { margin: 0; font-size: 12.5px; line-height: 1.5; }

.pinned-when {
  font-family: var(--font-mono); font-size: 11px; color: var(--ink-500);
  text-align: right;
}

[data-anim] { animation: fade-up var(--dur-slow) var(--ease-emphasized) both; }
[data-anim="enter-1"] { animation-delay: 60ms; }
[data-anim="enter-2"] { animation-delay: 160ms; }
[data-anim="enter-3"] { animation-delay: 220ms; }
@keyframes fade-up {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  [data-anim] { animation: none; }
}
</style>
