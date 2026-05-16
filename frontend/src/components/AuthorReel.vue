<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { CurationEntry, TrendingItem } from '@/types'

interface ReelEntry {
  id: string | number
  author: TrendingItem
  signature?: { plugin_id: string; display_name: string; latest_version?: string | null; summary?: string | null; icon_url?: string | null }
  signatureKind: 'curated' | 'best' | 'none'
}

const props = defineProps<{
  curated?: CurationEntry[]
  trending?: TrendingItem[]
}>()

const palettes = ['', 'coral', 'lemon', 'mint', 'plum'] as const

const items = computed<ReelEntry[]>(() => {
  const merged = new Map<string, ReelEntry>()

  for (const entry of props.curated || []) {
    if (entry.target_type !== 'author' || !entry.author) continue
    if (merged.has(entry.author.author_id)) continue
    const trendingMatch = (props.trending || []).find((t) => t.author_id === entry.author!.author_id)
    merged.set(entry.author.author_id, {
      id: entry.id,
      author: trendingMatch ?? {
        author_id: entry.author.author_id,
        github_login: entry.author.github_login,
        display_name: entry.author.display_name,
        avatar_url: entry.author.avatar_url,
        plugins_count: 0,
        likes_received: 0,
        downloads_total: 0,
      },
      signature: entry.signature_plugin
        ? {
            plugin_id: entry.signature_plugin.plugin_id,
            display_name: entry.signature_plugin.display_name,
            latest_version: entry.signature_plugin.latest_version,
            summary: entry.signature_plugin.summary,
            icon_url: entry.signature_plugin.icon_url,
          }
        : trendingMatch?.best_plugin
          ? {
              plugin_id: trendingMatch.best_plugin.plugin_id,
              display_name: trendingMatch.best_plugin.display_name,
              latest_version: trendingMatch.best_plugin.latest_version,
              summary: trendingMatch.best_plugin.summary,
              icon_url: trendingMatch.best_plugin.icon_url,
            }
          : undefined,
      signatureKind: entry.signature_plugin
        ? 'curated'
        : trendingMatch?.best_plugin
          ? 'best'
          : 'none',
    })
  }

  for (const author of props.trending || []) {
    if (merged.has(author.author_id)) continue
    merged.set(author.author_id, {
      id: author.author_id,
      author,
      signature: author.best_plugin
        ? {
            plugin_id: author.best_plugin.plugin_id,
            display_name: author.best_plugin.display_name,
            latest_version: author.best_plugin.latest_version,
            summary: author.best_plugin.summary,
            icon_url: author.best_plugin.icon_url,
          }
        : undefined,
      signatureKind: author.best_plugin ? 'best' : 'none',
    })
  }

  return Array.from(merged.values()).slice(0, 12)
})

/** 一次显示 2 张大卡，并排 + 垂直翻页 */
const PAGE_SIZE = 2
const totalPages = computed(() => Math.max(1, Math.ceil(items.value.length / PAGE_SIZE)))
const page = ref(0)

const pages = computed(() => {
  const buckets: ReelEntry[][] = []
  for (let i = 0; i < items.value.length; i += PAGE_SIZE) {
    buckets.push(items.value.slice(i, i + PAGE_SIZE))
  }
  return buckets.length ? buckets : [[]]
})

watch(() => totalPages.value, (n) => {
  if (page.value >= n) page.value = Math.max(0, n - 1)
})

function paletteOf(idx: number): string {
  return palettes[idx % palettes.length]
}

const containerRef = ref<HTMLElement | null>(null)
let lastWheelAt = 0

function next(): void { if (page.value < totalPages.value - 1) page.value += 1 }
function prev(): void { if (page.value > 0) page.value -= 1 }

function onWheel(e: WheelEvent): void {
  if (totalPages.value <= 1) return
  if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return
  const now = performance.now()
  const wantNext = e.deltaY > 0
  const wantPrev = e.deltaY < 0
  const atFirst = page.value === 0
  const atLast = page.value === totalPages.value - 1
  if ((wantNext && atLast) || (wantPrev && atFirst)) return
  e.preventDefault()
  if (now - lastWheelAt < 380) return
  lastWheelAt = now
  if (wantNext) next()
  else if (wantPrev) prev()
}

onMounted(() => {
  containerRef.value?.addEventListener('wheel', onWheel, { passive: false })
})
onBeforeUnmount(() => {
  containerRef.value?.removeEventListener('wheel', onWheel)
})
</script>

<template>
  <div v-if="items.length" class="ar" ref="containerRef">
    <!-- 左侧垂直进度条 -->
    <div v-if="totalPages > 1" class="ar-progress" role="tablist" aria-label="作者翻页">
      <button
        v-for="i in totalPages"
        :key="i"
        type="button"
        :aria-current="page === i - 1 ? 'true' : undefined"
        :aria-label="`第 ${i} 位`"
        class="ar-tick"
        @click="page = i - 1"
      ></button>
    </div>

    <div class="ar-viewport">
      <div class="ar-rail" :style="{ transform: `translateY(-${page * 100}%)` }">
        <div v-for="(group, groupIdx) in pages" :key="groupIdx" class="ar-page">
          <article
            v-for="(item, j) in group"
            :key="item.id"
            class="ar-card"
          >
            <!-- 右上角淡黄色装饰球（被卡片裁切） -->
            <div class="ar-deco" aria-hidden="true"></div>

            <!-- 头部：kicker / 大头像 / 名字 + login + bio -->
            <header class="ar-head">
              <span class="ar-kicker">— FEATURED · 本期作者</span>

              <div class="ar-who">
                <router-link
                  :to="{ name: 'author', params: { id: item.author.author_id } }"
                  class="ar-av-link"
                >
                  <span :class="['ar-av', paletteOf(groupIdx * PAGE_SIZE + j)]" aria-hidden="true">
                    <img v-if="item.author.avatar_url" :src="item.author.avatar_url" :alt="item.author.display_name">
                    <template v-else>{{ item.author.display_name[0]?.toUpperCase() || '?' }}</template>
                  </span>
                </router-link>

                <div class="ar-text">
                  <router-link
                    :to="{ name: 'author', params: { id: item.author.author_id } }"
                    class="ar-name-link"
                  >
                    <h4>{{ item.author.display_name }}</h4>
                  </router-link>
                  <span class="ar-login">@{{ item.author.github_login }}</span>
                  <p v-if="item.author.bio" class="ar-bio">{{ item.author.bio }}</p>
                  <p v-else class="ar-bio is-empty">这位作者还没有填写公开 Bio。</p>
                </div>
              </div>

              <dl class="ar-stats">
                <div>
                  <dt>插件</dt>
                  <dd>{{ item.author.plugins_count }}</dd>
                </div>
                <div>
                  <dt>获赞</dt>
                  <dd>{{ item.author.likes_received }}</dd>
                </div>
                <div>
                  <dt>下载</dt>
                  <dd>{{ item.author.downloads_total }}</dd>
                </div>
                <div>
                  <dt>均分</dt>
                  <dd>{{ item.author.rating_count ? item.author.rating_avg?.toFixed(1) : '--' }}</dd>
                </div>
              </dl>
            </header>

            <!-- 代表作 panel -->
            <router-link
              v-if="item.signature"
              :to="{ name: 'plugin', params: { id: item.signature.plugin_id } }"
              class="ar-sig"
            >
              <span :class="['ar-sig-icon', paletteOf(groupIdx * PAGE_SIZE + j)]" aria-hidden="true">
                <img v-if="item.signature.icon_url" :src="item.signature.icon_url" :alt="item.signature.display_name">
                <template v-else>{{ item.signature.display_name[0]?.toUpperCase() || '?' }}</template>
              </span>
              <div class="ar-sig-info">
                <div class="ar-sig-line">
                  <b>{{ item.signature.display_name }}</b>
                  <small>{{ item.signature.plugin_id }}<template v-if="item.signature.latest_version"> · v{{ item.signature.latest_version }}</template></small>
                </div>
                <p v-if="item.signature.summary">{{ item.signature.summary }}</p>
                <p v-else class="ar-sig-empty">{{ item.signatureKind === 'curated' ? '运营手挑代表作' : '该作者数据最高的作品' }}</p>
              </div>
            </router-link>
            <div v-else class="ar-sig is-empty">
              <span class="ar-sig-icon" aria-hidden="true">·</span>
              <div class="ar-sig-info">
                <div class="ar-sig-line">
                  <b>暂无作品</b>
                </div>
                <p>这位作者还没有公开作品。</p>
              </div>
            </div>
          </article>
          <div v-if="group.length === 1" class="ar-card ar-card-spacer" aria-hidden="true"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ar {
  position: relative;
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: 0;
  height: 360px;
  border-radius: var(--radius-lg);
  border: 1.5px solid var(--line);
  background: var(--surface);
  overflow: hidden;
}
@media (max-width: 720px) {
  .ar { grid-template-columns: 22px 1fr; height: auto; min-height: 420px; }
}

/* 左侧垂直进度条 */
.ar-progress {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 8px;
  padding: var(--space-3) 0;
  background: var(--surface-soft);
  border-right: 1px dashed var(--line);
}
.ar-tick {
  width: 6px; height: 22px;
  border-radius: 999px;
  background: var(--ink-200);
  transition: height var(--dur-base) var(--ease-emphasized),
              background var(--dur-fast);
}
.ar-tick:hover { background: var(--ink-500); }
.ar-tick[aria-current="true"] { background: var(--coral); height: 36px; }

.ar-viewport {
  position: relative;
  overflow: hidden;
  height: 100%;
}
.ar-rail {
  display: grid;
  grid-auto-flow: row;
  grid-auto-rows: 100%;
  height: 100%;
  transition: transform var(--dur-slow) var(--ease-emphasized);
}

.ar-page {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
  padding: var(--space-3);
  height: 100%;
}
@media (max-width: 720px) {
  .ar-page { grid-template-columns: 1fr; }
  .ar-card-spacer { display: none; }
}

/* === 单张大卡 === */
.ar-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  overflow: hidden;
  height: 100%;
  min-height: 0;
  transition: border-color var(--dur-base), transform var(--dur-base) var(--ease-emphasized), box-shadow var(--dur-base);
}
.ar-card:hover {
  border-color: var(--ink-900);
  transform: translate(-2px, -2px);
  box-shadow: var(--shadow-poster);
}
.ar-card-spacer { background: transparent; border-color: transparent; pointer-events: none; box-shadow: none; transform: none; }

/* 右上角淡黄装饰球 */
.ar-deco {
  position: absolute;
  top: -38px; right: -42px;
  width: 160px; height: 160px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--lemon) 0%, #ffe9a8 70%, transparent 100%);
  opacity: 0.78;
  pointer-events: none;
  z-index: 0;
}
/* 让所有"内容"层在球之上；球本身保持 absolute */
.ar-card > *:not(.ar-deco) { position: relative; z-index: 1; }

/* === 头部 === */
.ar-head {
  display: grid; gap: var(--space-3);
  align-content: start;
  flex: 1 1 auto;        /* 占满剩余空间 */
  min-height: 0;
}
.ar-kicker {
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 12px; color: var(--coral);
  font-weight: 700;
}

.ar-who {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--space-4);
  align-items: flex-start;
}
.ar-av-link { display: block; }
.ar-av {
  display: grid; place-items: center;
  width: 64px; height: 64px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--blue-500), var(--blue-700));
  color: var(--ink-on-blue);
  font-family: var(--font-display); font-weight: 800; font-size: 24px;
  overflow: hidden;
  box-shadow: var(--shadow-poster-soft);
  transition: transform var(--dur-base) var(--ease-pop);
}
.ar-av-link:hover .ar-av { transform: rotate(-3deg) scale(1.04); }
.ar-av.coral { background: linear-gradient(135deg, var(--coral), #ff8a8d); color: #fff; }
.ar-av.lemon { background: linear-gradient(135deg, var(--lemon), #ffaa3a); color: var(--ink-900); }
.ar-av.mint  { background: linear-gradient(135deg, var(--mint), #28a585);  color: #fff; }
.ar-av.plum  { background: linear-gradient(135deg, var(--plum), #5a3fd9);  color: #fff; }
.ar-av img { width: 100%; height: 100%; object-fit: cover; }

.ar-text {
  display: grid; gap: 2px; min-width: 0;
}
.ar-name-link { color: inherit; text-decoration: none; }
.ar-name-link:hover h4 { color: var(--blue-700); }
.ar-text h4 {
  margin: 0;
  font-family: var(--font-display); font-weight: 900;
  font-size: 18px; line-height: 1.18;
  color: var(--ink-900);
  transition: color var(--dur-fast);
}
.ar-login {
  font-family: var(--font-mono); font-size: 12.5px;
  color: var(--ink-500);
  margin-bottom: 4px;
}
.ar-bio {
  margin: 6px 0 0;
  font-size: 12.5px; color: var(--ink-700);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.ar-bio.is-empty {
  color: var(--ink-300);
  font-style: italic;
}

.ar-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
}
.ar-stats div {
  display: grid;
  gap: 3px;
  min-width: 0;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(135, 154, 185, 0.26);
}
.ar-stats dt {
  margin: 0;
  font-family: var(--font-brand);
  letter-spacing: 0.08em;
  font-size: 10.5px;
  color: var(--ink-500);
}
.ar-stats dd {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 900;
  font-size: 17px;
  line-height: 1;
  color: var(--ink-900);
}

/* === 代表作 panel === */
.ar-sig {
  flex: 0 0 auto;        /* 永远贴底部，不被压缩 */
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--space-3);
  align-items: center;
  padding: var(--space-3) var(--space-4);
  background: var(--blue-50);
  border: 1.5px dashed var(--blue-300);
  border-radius: var(--radius-md);
  color: inherit;
  text-decoration: none;
  transition: background var(--dur-fast), border-color var(--dur-fast), transform var(--dur-fast);
}
.ar-sig:hover {
  background: var(--blue-100);
  border-color: var(--blue-500);
  transform: translateY(-1px);
}
.ar-sig.is-empty {
  background: var(--surface-soft);
  border-color: var(--line);
  color: var(--ink-500);
}

.ar-sig-icon {
  width: 44px; height: 44px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--blue-500), var(--blue-700));
  color: var(--ink-on-blue);
  display: grid; place-items: center;
  font-family: var(--font-display); font-weight: 800; font-size: 18px;
  flex: 0 0 auto;
  overflow: hidden;
  box-shadow: var(--shadow-poster-soft);
}
.ar-sig-icon.coral { background: linear-gradient(135deg, var(--coral), #ff8a8d); color: #fff; }
.ar-sig-icon.lemon { background: linear-gradient(135deg, var(--lemon), #ffaa3a); color: var(--ink-900); }
.ar-sig-icon.mint  { background: linear-gradient(135deg, var(--mint), #28a585);  color: #fff; }
.ar-sig-icon.plum  { background: linear-gradient(135deg, var(--plum), #5a3fd9);  color: #fff; }
.ar-sig-icon img { width: 100%; height: 100%; object-fit: cover; }
.ar-sig.is-empty .ar-sig-icon {
  background: var(--surface-hover);
  color: var(--ink-300);
  box-shadow: none;
}

.ar-sig-info { display: grid; gap: 4px; min-width: 0; }
.ar-sig-line {
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px;
  min-width: 0;
}
.ar-sig-line b {
  font-family: var(--font-display); font-weight: 900;
  font-size: 14px; line-height: 1.18;
  color: var(--blue-700);
}
.ar-sig-line small {
  font-family: var(--font-mono); font-size: 11.5px;
  color: var(--ink-500);
}
.ar-sig-info p {
  margin: 0;
  font-size: 13px; color: var(--ink-700);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.ar-sig-info p.ar-sig-empty {
  color: var(--ink-500);
  font-style: italic;
}

@media (max-width: 720px) {
  .ar-card { padding: var(--space-3) var(--space-4); }
  .ar-av { width: 56px; height: 56px; font-size: 22px; }
  .ar-text h4 { font-size: 17px; }
  .ar-bio { -webkit-line-clamp: 2; }
  .ar-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (prefers-reduced-motion: reduce) {
  .ar-rail { transition: none; }
  .ar-tick { transition: none; }
  .ar-av { transition: none; }
}
</style>
