<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount } from 'vue';
import api from '@/api';
import {
  formatNumber,
  formatRelative,
  formatDate,
  formatUptime,
  statusText,
} from '@/utils/format';
import type { SystemInfo, DashboardData, Plugin } from '@/types';
import PageSkeleton from '@/components/PageSkeleton.vue';
import EmptyState from '@/components/EmptyState.vue';

const system = ref<SystemInfo | null>(null);
const dashboard = ref<DashboardData | null>(null);
const pendingPlugins = ref<Plugin[]>([]);
const loading = ref(true);
const error = ref('');
let requestId = 0;

async function loadAll() {
  const current = ++requestId;
  loading.value = true;
  error.value = '';
  try {
    const [sys, dash, pluginResult] = await Promise.all([
      api.get<SystemInfo>('/api/v1/admin/system'),
      api.get<DashboardData>('/api/v1/admin/dashboard'),
      api.get<{ items: Plugin[] }>('/api/v1/admin/plugins'),
    ]);
    if (current !== requestId) return;
    system.value = sys;
    dashboard.value = dash;
    pendingPlugins.value = (pluginResult.items || [])
      .filter((p) => p.status === 'pending_review')
      .slice(0, 8);
  } catch (e) {
    if (current === requestId)
      error.value = (e as Error).message || '无法读取仪表盘';
  } finally {
    if (current === requestId) loading.value = false;
  }
}

const activityMax = computed(() => {
  const peaks = (dashboard.value?.activity || []).flatMap((d) => [
    d.plugins_created,
    d.comments_created,
    d.ratings_created,
  ]);
  return Math.max(1, ...peaks);
});

function barHeight(value: number): string {
  return (
    Math.max(0, Math.round(((value || 0) / activityMax.value) * 88)) + 'px'
  );
}

const pluginBreakdown = computed(() =>
  Object.entries(dashboard.value?.plugin_status_breakdown || {})
    .filter(([, v]) => Number(v) > 0)
    .map(([key, value]) => ({ key, value: Number(value) }))
    .sort((a, b) => b.value - a.value),
);

const versionBreakdown = computed(() =>
  Object.entries(dashboard.value?.version_status_breakdown || {})
    .filter(([, v]) => Number(v) > 0)
    .map(([key, value]) => ({ key, value: Number(value) }))
    .sort((a, b) => b.value - a.value),
);

onMounted(loadAll);
onBeforeUnmount(() => {
  requestId++;
});
</script>

<template>
  <PageSkeleton v-if="loading" type="detail" />
  <div v-else-if="error" class="admin-error" role="alert">
    <p>{{ error }}</p>
    <button class="btn" @click="loadAll">重新加载</button>
  </div>

  <div v-else class="dashboard-view">
    <section v-if="system && dashboard" class="dash-hero">
      <div>
        <h1 class="desk-title">市场运行总览</h1>
        <p>值班简报 · 市场活动、审核队列与服务记录</p>
      </div>
      <RouterLink :to="{ name: 'admin-plugins' }" class="dash-assignment">
        <span>待审核插件</span><strong>{{ formatNumber(dashboard.stats.pending_plugins) }}</strong>
        <small>前往插件治理 ↗</small>
      </RouterLink>
    </section>

    <section v-if="dashboard" class="dash-metrics">
      <article class="dash-metric">
        <span class="kicker-mini">插件</span>
        <strong>{{ formatNumber(dashboard.stats.plugins_total) }}</strong>
        <small>{{ dashboard.stats.pending_plugins }} 待审核</small>
      </article>
      <article class="dash-metric">
        <span class="kicker-mini">版本</span>
        <strong>{{ formatNumber(dashboard.stats.versions_total) }}</strong>
        <small>{{ dashboard.stats.pending_versions }} 待审核</small>
      </article>
      <article class="dash-metric">
        <span class="kicker-mini">互动</span>
        <strong
          >{{ formatNumber(dashboard.stats.comments_total) }} /
          {{ formatNumber(dashboard.stats.ratings_total) }}</strong
        >
        <small>评论 / 评分</small>
      </article>
      <article class="dash-metric">
        <span class="kicker-mini">使用</span>
        <strong
          >{{ formatNumber(dashboard.stats.likes_total) }} /
          {{ formatNumber(dashboard.stats.downloads_total) }}</strong
        >
        <small>订阅 / 下载</small>
      </article>
      <article class="dash-metric">
        <span class="kicker-mini">社区</span>
        <strong
          >{{ formatNumber(dashboard.stats.authors_total) }} /
          {{ formatNumber(dashboard.stats.webhooks_total) }}</strong
        >
        <small>作者 / Webhook</small>
      </article>
    </section>

    <!-- 主区：活动 + pending -->
    <section v-if="dashboard" class="dash-main">
      <article class="dash-card dash-activity">
        <header class="dash-card-head">
          <div>
            <h2>最近 7 天活动</h2>
          </div>
          <div class="dash-activity-legend">
            <span
              ><i class="dot dot-plugin" aria-hidden="true"></i>新增插件</span
            >
            <span><i class="dot dot-comment" aria-hidden="true"></i>评论</span>
            <span><i class="dot dot-rating" aria-hidden="true"></i>评分</span>
          </div>
        </header>

        <div class="dash-activity-chart">
          <div
            v-for="day in dashboard.activity || []"
            :key="day.date"
            class="dash-activity-day"
          >
            <div class="bars">
              <span
                class="bar plugin"
                :style="{ height: barHeight(day.plugins_created) }"
                v-market-tooltip="`新增插件 ${day.plugins_created || 0}`"
                tabindex="0"
                :aria-label="`新增插件 ${day.plugins_created || 0}`"
              ></span>
              <span
                class="bar comment"
                :style="{ height: barHeight(day.comments_created) }"
                v-market-tooltip="`评论 ${day.comments_created || 0}`"
                tabindex="0"
                :aria-label="`评论 ${day.comments_created || 0}`"
              ></span>
              <span
                class="bar rating"
                :style="{ height: barHeight(day.ratings_created) }"
                v-market-tooltip="`评分 ${day.ratings_created || 0}`"
                tabindex="0"
                :aria-label="`评分 ${day.ratings_created || 0}`"
              ></span>
            </div>
            <strong>{{ day.date ? day.date.slice(5) : '--' }}</strong>
            <small
              >{{
                (day.plugins_created || 0) +
                (day.comments_created || 0) +
                (day.ratings_created || 0)
              }}
              动态</small
            >
          </div>
        </div>

        <div class="dash-breakdown-row">
          <div>
            <span class="kicker-mini">插件状态</span>
            <ul>
              <li v-for="item in pluginBreakdown" :key="item.key">
                <span :class="['badge', `status-${item.key}`]">{{
                  statusText(item.key)
                }}</span>
                <b>{{ item.value }}</b>
              </li>
            </ul>
          </div>
          <div>
            <span class="kicker-mini">版本状态</span>
            <ul>
              <li v-for="item in versionBreakdown" :key="item.key">
                <span :class="['badge', `status-${item.key}`]">{{
                  statusText(item.key)
                }}</span>
                <b>{{ item.value }}</b>
              </li>
            </ul>
          </div>
        </div>
      </article>

      <article class="dash-card dash-pending">
        <header class="dash-card-head">
          <div>
            <h2>待审核插件</h2>
          </div>
        </header>

        <div v-if="pendingPlugins.length" class="dash-pending-list">
          <article
            v-for="p in pendingPlugins"
            :key="p.plugin_id"
            class="dash-pending-item"
          >
            <div class="dash-pending-icon" aria-hidden="true">
              <img v-if="p.icon_url" :src="p.icon_url" :alt="p.display_name" />
              <template v-else>{{
                p.display_name[0]?.toUpperCase() || '?'
              }}</template>
            </div>
            <div class="dash-pending-info">
              <strong>{{ p.display_name }}</strong>
              <small
                >{{ p.plugin_id }} · @{{ p.owner_login || p.owner_id }}</small
              >
              <p>{{ p.summary }}</p>
            </div>
            <div class="dash-pending-meta">
              <small>{{ formatRelative(p.updated_at) }}</small>
            </div>
          </article>
        </div>
        <EmptyState v-else title="队列为空" message="当前没有插件等待审核。" />
      </article>
    </section>

    <!-- 底部服务条 -->
    <section v-if="system" class="dash-system" aria-label="服务记录">
      <h2>服务记录</h2>
      <div>
        <span class="kicker-mini">服务健康</span>
        <strong>{{
          system.status === 'ok' ? '正常' : '⚠ ' + system.status
        }}</strong>
      </div>
      <div>
        <span class="kicker-mini">数据库</span>
        <strong>{{ system.database }}</strong>
        <small>{{ system.database_path || '内存数据库' }}</small>
      </div>
      <div>
        <span class="kicker-mini">审核模式</span>
        <strong>{{ system.review_required ? '人工审核' : '快速发布' }}</strong>
        <small
          >最近审核 {{ formatRelative(system.stats.latest_review_at) }}</small
        >
      </div>
      <div>
        <span class="kicker-mini">启动时间</span>
        <strong>{{ formatDate(system.started_at) }}</strong>
        <small>已运行 {{ formatUptime(system.uptime_seconds) }}</small>
      </div>
      <div><span class="kicker-mini">运行环境</span><strong>{{ system.environment }}</strong></div>
      <div><span class="kicker-mini">GitHub OAuth</span><strong>{{ system.github_oauth_configured ? '已接通' : '未配置' }}</strong></div>
      <div><span class="kicker-mini">GitHub Webhook</span><strong>{{ system.github_webhook_configured ? '在线' : '未配置' }}</strong></div>
    </section>
  </div>
</template>

<style scoped>
.dashboard-view {
  display: grid;
  gap: 20px;
}
.dash-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 20px;
  padding: clamp(16px, 2.6vw, 32px) 0;
  border-top: 3px double var(--ink-700);
}
.dash-hero p {
  margin: 10px 0 0;
  color: var(--ink-500);
  font-size: 13px;
}
.dash-assignment {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px 12px;
  align-items: baseline;
  padding-left: 18px;
  border-left: 2px solid var(--blue-600);
  color: var(--ink-700);
  font-size: 13px;
}
.dash-assignment strong {
  grid-row: span 2;
  font: 650 clamp(30px, 4vw, 48px)/1 var(--font-editorial);
  color: var(--blue-700);
}
.dash-assignment small { color: var(--blue-700); }
.dash-assignment:hover small { text-decoration: underline; }
.kicker-mini { font: 12px var(--font-sans); color: var(--ink-500); }
.dash-metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  border-block: 1px solid var(--ink-700);
  background: var(--surface);
  overflow: hidden;
}
.dash-metric {
  display: grid;
  gap: 9px;
  padding: 22px 18px;
  border-right: 1px solid var(--line);
}
.dash-metric:last-child {
  border: 0;
}
.dash-metric strong {
  font: 650 clamp(22px, 2.4vw, 32px)/1.15 var(--font-editorial);
  overflow-wrap: anywhere;
  color: var(--ink-900);
}
.dash-metric small {
  font-size: 11px;
  color: var(--ink-500);
}
.dash-main {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
  gap: 20px;
}
.dash-card {
  min-width: 0;
  padding: 18px 0;
  border-top: 3px double var(--ink-700);
}
.dash-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 15px;
  flex-wrap: wrap;
  margin-bottom: 22px;
}
.dash-card-head h2 {
  font: 650 21px var(--font-editorial);
  margin: 0;
}
.dash-activity-legend {
  display: flex;
  gap: 10px;
  color: var(--ink-500);
  font-size: 10px;
}
.dash-activity-legend span {
  display: flex;
  align-items: center;
  gap: 4px;
}
.dot {
  width: 6px;
  height: 6px;
  display: block;
}
.dot-plugin,
.bar.plugin {
  background: var(--blue-500);
}
.dot-comment,
.bar.comment {
  background: var(--coral);
}
.dot-rating,
.bar.rating {
  background: var(--mint);
}
.dash-activity-chart {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 8px;
  padding: 14px 0;
  border-block: 1px solid var(--line);
  overflow-x: auto;
}
.dash-activity-day {
  display: grid;
  gap: 7px;
  justify-items: center;
  font: 10px var(--font-mono);
  color: var(--ink-500);
}
.dash-activity-day .bars {
  height: 88px;
  display: flex;
  align-items: flex-end;
  gap: 3px;
}
.bar {
  width: 7px;
}
.dash-activity-day strong {
  color: var(--ink-900);
}
.dash-breakdown-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-top: 24px;
}
.dash-breakdown-row ul {
  padding: 0;
  margin: 10px 0 0;
  list-style: none;
}
.dash-breakdown-row li {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--line);
  font-size: 12px;
}
.dash-pending-list {
  display: grid;
}
.dash-pending-item {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
  padding: 15px 0;
  border-top: 1px solid var(--line);
}
.dash-pending-icon {
  width: 34px;
  height: 34px;
  background: var(--surface-soft);
  border: 1px solid var(--line);
  display: grid;
  place-items: center;
  color: var(--blue-500);
  overflow: hidden;
  border-radius: 3px;
}
.dash-pending-icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.dash-pending-info {
  display: grid;
  gap: 5px;
  min-width: 0;
}
.dash-pending-info strong {
  font-size: 13px;
}
.dash-pending-info small,
.dash-pending-meta small {
  font: 10px var(--font-mono);
  color: var(--ink-500);
  overflow-wrap: anywhere;
}
.dash-pending-info p {
  margin: 0;
  color: var(--ink-500);
  font-size: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.dash-pending-meta {
  display: grid;
  justify-items: end;
  gap: 8px;
}
.dash-system {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border-block: 1px solid var(--line);
  padding: 20px 0;
}
.dash-system h2 { grid-column: 1/-1; }
.dash-system > div {
  display: grid;
  gap: 7px;
  padding: 8px 12px;
  border-right: 1px solid var(--line);
  min-width: 0;
}
.dash-system > div:last-child {
  border: 0;
}
.dash-system strong {
  font-size: 12px;
  overflow-wrap: anywhere;
}
.dash-system small {
  font: 10px var(--font-mono);
  color: var(--ink-500);
  overflow-wrap: anywhere;
}
@media (max-width: 1100px) {
  .dash-main {
    grid-template-columns: 1fr;
  }
  .dash-metrics {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .dash-metric {
    border-bottom: 1px solid var(--line);
  }
}
@media (max-width: 600px) {
  .dash-metrics,
  .dash-system {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .dash-hero,
  .dash-card {
    padding: 12px 0;
  }
  .dash-hero { grid-template-columns: 1fr; }
  .dash-assignment { justify-self: start; }
  .dash-system {
    gap: 20px;
  }
  .dash-pending-item {
    grid-template-columns: 30px minmax(0, 1fr);
  }
  .dash-pending-meta {
    grid-column: 2;
    display: flex;
  }
  .dash-breakdown-row {
    gap: 15px;
  }
}
</style>
