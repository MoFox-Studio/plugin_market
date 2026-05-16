<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import api from '@/api'
import { formatNumber, formatRelative, formatDate, formatUptime, statusText } from '@/utils/format'
import type { SystemInfo, DashboardData, ActivityDay, Plugin } from '@/types'
import EmptyState from '@/components/EmptyState.vue'

const system = ref<SystemInfo | null>(null)
const dashboard = ref<DashboardData | null>(null)
const pendingPlugins = ref<Plugin[]>([])
const loading = ref(true)

async function loadAll() {
  loading.value = true
  try {
    const [sys, dash, pluginResult] = await Promise.all([
      api.get<SystemInfo>('/api/v1/admin/system'),
      api.get<DashboardData>('/api/v1/admin/dashboard'),
      api.get<{ items: Plugin[] }>('/api/v1/admin/plugins'),
    ])
    system.value = sys
    dashboard.value = dash
    pendingPlugins.value = (pluginResult.items || [])
      .filter((p) => p.status === 'pending_review')
      .slice(0, 8)
  } finally {
    loading.value = false
  }
}

const activityMax = computed(() => {
  const peaks = (dashboard.value?.activity || []).flatMap((d) => [d.plugins_created, d.comments_created, d.ratings_created])
  return Math.max(1, ...peaks)
})

function barHeight(value: number): string {
  return Math.max(6, Math.round((value || 0) / activityMax.value * 88)) + 'px'
}

const pluginBreakdown = computed(() =>
  Object.entries(dashboard.value?.plugin_status_breakdown || {})
    .filter(([, v]) => Number(v) > 0)
    .map(([key, value]) => ({ key, value: Number(value) }))
    .sort((a, b) => b.value - a.value),
)

const versionBreakdown = computed(() =>
  Object.entries(dashboard.value?.version_status_breakdown || {})
    .filter(([, v]) => Number(v) > 0)
    .map(([key, value]) => ({ key, value: Number(value) }))
    .sort((a, b) => b.value - a.value),
)

onMounted(loadAll)
</script>

<template>
  <div v-if="loading" class="dashboard-loading">加载中…</div>

  <div v-else class="dashboard-view">
    <!-- HERO -->
    <section v-if="system" class="dash-hero" data-anim="enter-1">
      <div class="dash-hero-bg" aria-hidden="true"></div>
      <div class="dash-hero-inner">
        <div class="dash-hero-left">
          <span class="kicker">CONTROL ROOM</span>
          <h1>仪表盘</h1>
          <p>市场概况一眼可见。需要做事请直接进入插件治理 / 版本治理 / 公告管理等左侧入口。</p>
        </div>
        <div class="dash-hero-pills">
          <span class="pill">{{ system.environment }}</span>
          <span class="pill">运行 {{ formatUptime(system.uptime_seconds) }}</span>
          <span class="pill">OAuth {{ system.github_oauth_configured ? '已接通' : '未配置' }}</span>
          <span class="pill">Webhook {{ system.github_webhook_configured ? '在线' : '未配置' }}</span>
        </div>
      </div>
    </section>

    <!-- 5 大数据 -->
    <section v-if="dashboard" class="dash-metrics" data-anim="enter-2">
      <article class="dash-metric">
        <span class="kicker-mini">PLUGINS</span>
        <strong>{{ formatNumber(dashboard.stats.plugins_total) }}</strong>
        <small>{{ dashboard.stats.pending_plugins }} 待审核</small>
      </article>
      <article class="dash-metric">
        <span class="kicker-mini">VERSIONS</span>
        <strong>{{ formatNumber(dashboard.stats.versions_total) }}</strong>
        <small>{{ dashboard.stats.pending_versions }} 待审核</small>
      </article>
      <article class="dash-metric">
        <span class="kicker-mini">ENGAGEMENT</span>
        <strong>{{ formatNumber(dashboard.stats.comments_total) }} / {{ formatNumber(dashboard.stats.ratings_total) }}</strong>
        <small>评论 / 评分</small>
      </article>
      <article class="dash-metric">
        <span class="kicker-mini">REACH</span>
        <strong>{{ formatNumber(dashboard.stats.likes_total) }} / {{ formatNumber(dashboard.stats.downloads_total) }}</strong>
        <small>点赞 / 下载</small>
      </article>
      <article class="dash-metric">
        <span class="kicker-mini">ECOSYSTEM</span>
        <strong>{{ formatNumber(dashboard.stats.authors_total) }} / {{ formatNumber(dashboard.stats.webhooks_total) }}</strong>
        <small>作者 / Webhook</small>
      </article>
    </section>

    <!-- 主区：活动 + pending -->
    <section v-if="dashboard" class="dash-main" data-anim="enter-3">
      <article class="dash-card dash-activity">
        <header class="dash-card-head">
          <div>
            <span class="kicker-mini">7 DAYS · 市场动态</span>
            <h2>最近 7 天活动</h2>
          </div>
          <div class="dash-activity-legend">
            <span><i class="dot dot-plugin" aria-hidden="true"></i>新增插件</span>
            <span><i class="dot dot-comment" aria-hidden="true"></i>评论</span>
            <span><i class="dot dot-rating" aria-hidden="true"></i>评分</span>
          </div>
        </header>

        <div class="dash-activity-chart">
          <div v-for="day in (dashboard.activity || [])" :key="day.date" class="dash-activity-day">
            <div class="bars">
              <span class="bar plugin" :style="{ height: barHeight(day.plugins_created) }" :title="`新增插件 ${day.plugins_created || 0}`"></span>
              <span class="bar comment" :style="{ height: barHeight(day.comments_created) }" :title="`评论 ${day.comments_created || 0}`"></span>
              <span class="bar rating" :style="{ height: barHeight(day.ratings_created) }" :title="`评分 ${day.ratings_created || 0}`"></span>
            </div>
            <strong>{{ day.date ? day.date.slice(5) : '--' }}</strong>
            <small>{{ (day.plugins_created || 0) + (day.comments_created || 0) + (day.ratings_created || 0) }} 动态</small>
          </div>
        </div>

        <div class="dash-breakdown-row">
          <div>
            <span class="kicker-mini">PLUGIN STATUS</span>
            <ul>
              <li v-for="item in pluginBreakdown" :key="item.key">
                <span :class="['badge', `status-${item.key}`]">{{ statusText(item.key) }}</span>
                <b>{{ item.value }}</b>
              </li>
            </ul>
          </div>
          <div>
            <span class="kicker-mini">VERSION STATUS</span>
            <ul>
              <li v-for="item in versionBreakdown" :key="item.key">
                <span :class="['badge', `status-${item.key}`]">{{ statusText(item.key) }}</span>
                <b>{{ item.value }}</b>
              </li>
            </ul>
          </div>
        </div>
      </article>

      <article class="dash-card dash-pending">
        <header class="dash-card-head">
          <div>
            <span class="kicker-mini">PENDING REVIEW</span>
            <h2>待审核插件</h2>
          </div>
          <router-link class="btn btn-sm" :to="{ name: 'admin-plugins' }">前往插件治理 →</router-link>
        </header>

        <div v-if="pendingPlugins.length" class="dash-pending-list">
          <article v-for="p in pendingPlugins" :key="p.plugin_id" class="dash-pending-item">
            <div class="dash-pending-icon" aria-hidden="true">
              <img v-if="p.icon_url" :src="p.icon_url" :alt="p.display_name">
              <template v-else>{{ p.display_name[0]?.toUpperCase() || '?' }}</template>
            </div>
            <div class="dash-pending-info">
              <strong>{{ p.display_name }}</strong>
              <small>{{ p.plugin_id }} · @{{ p.owner_login || p.owner_id }}</small>
              <p>{{ p.summary }}</p>
            </div>
            <div class="dash-pending-meta">
              <span class="badge status-pending_review">待审核</span>
              <small>{{ formatRelative(p.updated_at) }}</small>
            </div>
          </article>
        </div>
        <EmptyState v-else title="队列为空" message="当前没有插件等待审核。" />
      </article>
    </section>

    <!-- 底部服务条 -->
    <section v-if="system" class="dash-system" data-anim="enter-4">
      <div>
        <span class="kicker-mini">STATUS</span>
        <strong>{{ system.status === 'ok' ? '✓ Healthy' : '⚠ ' + system.status }}</strong>
      </div>
      <div>
        <span class="kicker-mini">DATABASE</span>
        <strong>{{ system.database }}</strong>
        <small>{{ system.database_path || '内存数据库' }}</small>
      </div>
      <div>
        <span class="kicker-mini">REVIEW MODE</span>
        <strong>{{ system.review_required ? '人工审核' : '快速发布' }}</strong>
        <small>最近审核 {{ formatRelative(system.stats.latest_review_at) }}</small>
      </div>
      <div>
        <span class="kicker-mini">STARTED AT</span>
        <strong>{{ formatDate(system.started_at) }}</strong>
        <small>已运行 {{ formatUptime(system.uptime_seconds) }}</small>
      </div>
    </section>
  </div>
</template>

<style scoped>
.dashboard-view {
  display: grid;
  gap: var(--space-6);
}

.dashboard-loading {
  text-align: center;
  padding: var(--space-12);
  color: var(--ink-500);
  font-family: var(--font-mono);
}

/* === HERO === */
.dash-hero {
  position: relative; overflow: hidden;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--blue-700) 0%, var(--blue-500) 60%, #5fb8ff 100%);
  color: #fff;
  padding: var(--space-6) var(--space-7);
  box-shadow: var(--shadow-poster);
}
.dash-hero-bg {
  position: absolute; inset: 0;
  background: var(--halftone);
  opacity: 0.18;
  mix-blend-mode: screen;
  pointer-events: none;
}
.dash-hero-inner {
  position: relative; z-index: 1;
  display: flex; justify-content: space-between; align-items: center;
  gap: var(--space-5); flex-wrap: wrap;
}
.dash-hero-left .kicker {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 12px; color: rgba(255,255,255,0.92);
}
.dash-hero-left .kicker::before { content: ""; width: 22px; height: 2px; background: var(--lemon); }
.dash-hero-left h1 {
  margin: 6px 0 6px;
  font-family: var(--font-display); font-weight: 900;
  font-size: clamp(28px, 3.4vw, 36px);
  line-height: 1.05;
}
.dash-hero-left p {
  margin: 0;
  opacity: 0.92;
  max-width: 56ch;
  font-size: 14px;
}
.dash-hero-pills { display: flex; gap: 8px; flex-wrap: wrap; }
.dash-hero-pills .pill {
  padding: 4px 10px;
  border-radius: var(--radius-pill);
  background: rgba(255,255,255,0.16);
  color: #fff;
  font-size: 12px; font-weight: 600;
  font-family: var(--font-mono);
}

/* === Metrics === */
.dash-metrics {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--space-3);
}
@media (max-width: 1024px) {
  .dash-metrics { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 480px) {
  .dash-metrics { grid-template-columns: 1fr; }
}

.dash-metric {
  display: grid; gap: 2px;
  padding: var(--space-4);
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
}
.dash-metric strong {
  font-family: var(--font-brand); letter-spacing: var(--letter-bebas);
  font-size: 28px; color: var(--ink-900); line-height: 1;
  margin-top: 4px;
}
.dash-metric small {
  font-family: var(--font-mono); font-size: 11.5px; color: var(--ink-500);
}

.kicker-mini {
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 11px; color: var(--ink-500); text-transform: uppercase;
}

/* === Main grid === */
.dash-main {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
  gap: var(--space-3);
}
@media (max-width: 1280px) {
  .dash-main { grid-template-columns: 1fr; }
}

.dash-card {
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  padding: var(--space-5);
  display: grid; gap: var(--space-4);
}
.dash-card-head {
  display: flex; justify-content: space-between; align-items: flex-end;
  gap: var(--space-3); flex-wrap: wrap;
}
.dash-card-head h2 {
  margin: 4px 0 0;
  font-family: var(--font-display); font-weight: 900;
  font-size: 20px; line-height: 1.15;
  color: var(--ink-900);
}

/* === Activity chart === */
.dash-activity-legend {
  display: flex; gap: 14px; flex-wrap: wrap;
  font-family: var(--font-mono); font-size: 11px;
  color: var(--ink-500);
}
.dash-activity-legend span { display: inline-flex; align-items: center; gap: 4px; }
.dash-activity-legend .dot {
  width: 8px; height: 8px; border-radius: 50%;
  display: inline-block;
}
.dash-activity-legend .dot-plugin  { background: var(--blue-500); }
.dash-activity-legend .dot-comment { background: var(--coral); }
.dash-activity-legend .dot-rating  { background: var(--lemon); }

.dash-activity-chart {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: var(--space-2);
  align-items: end;
  padding: var(--space-3) 0;
  border-top: 1px dashed var(--line);
  border-bottom: 1px dashed var(--line);
}
.dash-activity-day {
  display: grid;
  grid-template-rows: 88px auto auto;
  align-items: end; justify-items: center;
  gap: 4px;
  font-family: var(--font-mono); font-size: 10.5px; color: var(--ink-500);
}
.dash-activity-day strong {
  font-size: 11px; color: var(--ink-700); font-weight: 700;
  margin-top: 4px;
}
.dash-activity-day .bars {
  display: flex; gap: 2px;
  align-items: flex-end;
  height: 88px;
}
.dash-activity-day .bar {
  width: 7px;
  border-radius: 2px 2px 0 0;
  transition: opacity var(--dur-fast);
}
.dash-activity-day .bar:hover { opacity: 0.85; }
.dash-activity-day .bar.plugin  { background: var(--blue-500); }
.dash-activity-day .bar.comment { background: var(--coral); }
.dash-activity-day .bar.rating  { background: var(--lemon); }

.dash-breakdown-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}
@media (max-width: 600px) { .dash-breakdown-row { grid-template-columns: 1fr; } }
.dash-breakdown-row > div { display: grid; gap: 6px; }
.dash-breakdown-row ul {
  list-style: none; margin: 0; padding: 0;
  display: grid; gap: 4px;
}
.dash-breakdown-row li {
  display: flex; justify-content: space-between; align-items: center;
  padding: 4px 0;
  border-bottom: 1px dashed var(--line);
  font-size: 13px;
}
.dash-breakdown-row li:last-child { border-bottom: none; }
.dash-breakdown-row li b {
  font-family: var(--font-brand); letter-spacing: var(--letter-bebas);
  color: var(--ink-900);
  font-size: 16px;
}

/* === Pending list === */
.dash-pending-list { display: grid; gap: 8px; }
.dash-pending-item {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: var(--space-3);
  padding: 10px 12px;
  background: var(--surface-soft);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  align-items: center;
  transition: border-color var(--dur-fast), background var(--dur-fast);
}
.dash-pending-item:hover {
  border-color: var(--lemon);
  background: var(--surface);
}
.dash-pending-icon {
  width: 36px; height: 36px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--blue-500), var(--blue-700));
  color: var(--ink-on-blue);
  display: grid; place-items: center;
  font-family: var(--font-display); font-weight: 800; font-size: 14px;
  flex: 0 0 auto;
  overflow: hidden;
}
.dash-pending-icon img { width: 100%; height: 100%; object-fit: cover; }
.dash-pending-info { display: grid; gap: 2px; min-width: 0; }
.dash-pending-info strong {
  font-size: 13.5px; font-weight: 700; color: var(--ink-900);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.dash-pending-info small {
  font-family: var(--font-mono); font-size: 11px; color: var(--ink-500);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.dash-pending-info p {
  margin: 4px 0 0;
  font-size: 12px; color: var(--ink-700);
  display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden;
}
.dash-pending-meta { display: grid; gap: 4px; text-align: right; }
.dash-pending-meta small { font-family: var(--font-mono); font-size: 10.5px; color: var(--ink-500); }

/* === System bottom strip === */
.dash-system {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0;
  padding: var(--space-4) 0;
  border-top: 2px solid var(--ink-900);
  border-bottom: 2px solid var(--ink-900);
}
@media (max-width: 768px) { .dash-system { grid-template-columns: repeat(2, 1fr); gap: var(--space-3); padding: var(--space-3) var(--space-3); } }
.dash-system > div {
  padding: 0 var(--space-5);
  border-right: 1px dashed var(--line);
  display: grid; gap: 2px;
}
.dash-system > div:last-child { border-right: none; }
.dash-system strong {
  font-family: var(--font-display); font-weight: 700;
  font-size: 14px; color: var(--ink-900);
  margin-top: 4px;
}
.dash-system small {
  font-family: var(--font-mono); font-size: 11px; color: var(--ink-500);
}

[data-anim] { animation: fade-up var(--dur-slow) var(--ease-emphasized) both; }
[data-anim="enter-1"] { animation-delay: 60ms; }
[data-anim="enter-2"] { animation-delay: 140ms; }
[data-anim="enter-3"] { animation-delay: 200ms; }
[data-anim="enter-4"] { animation-delay: 260ms; }
@keyframes fade-up {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  [data-anim] { animation: none; }
}
</style>
