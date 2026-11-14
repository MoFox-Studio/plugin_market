<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import type { MarketStats } from '@/types';
import { formatNumber, formatUptime, parseApiDate } from '@/utils/format';

interface ProbeResult {
  ok: boolean;
  status: number | null;
  latencyMs: number | null;
  detail: string | null;
  payload: Record<string, unknown> | null;
  checkedAt: string | null;
}

const REFRESH_INTERVAL_MS = 30000;

const health = ref<ProbeResult | null>(null);
const ready = ref<ProbeResult | null>(null);
const statsProbe = ref<ProbeResult | null>(null);

const stats = ref<MarketStats | null>(null);
const startedAt = ref<string | null>(null);
const uptimeSeconds = ref<number | null>(null);
const lastRefreshedAt = ref<string | null>(null);
const refreshing = ref(false);
const now = ref(Date.now());
const pendingControllers = new Set<AbortController>();
let disposed = false;
let timer: number | null = null;
let uptimeTimer: number | null = null;

async function probe(path: string): Promise<ProbeResult> {
  const startedTs =
    typeof performance !== 'undefined' ? performance.now() : Date.now();
  const controller = new AbortController();
  pendingControllers.add(controller);
  const timeout = window.setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(path, {
      credentials: 'include',
      signal: controller.signal,
      cache: 'no-store',
    });
    const latencyMs = Math.round(
      (typeof performance !== 'undefined' ? performance.now() : Date.now()) -
        startedTs,
    );
    let payload: Record<string, unknown> | null = null;
    try {
      payload = await response.clone().json();
    } catch {
      payload = null;
    }
    const validObject =
      payload !== null &&
      typeof payload === 'object' &&
      !Array.isArray(payload);
    const validPayload =
      validObject &&
      (path === '/health'
        ? payload?.status === 'ok'
        : path === '/ready'
          ? payload?.status === 'ready' && payload?.database === 'ok'
          : typeof payload?.plugins_total === 'number');
    return {
      ok: response.ok && validPayload,
      status: response.status,
      latencyMs,
      detail: response.ok
        ? validPayload
          ? null
          : '接口没有返回有效的状态数据'
        : response.statusText || `HTTP ${response.status}`,
      payload,
      checkedAt: new Date().toISOString(),
    };
  } catch (err) {
    const latencyMs = Math.round(
      (typeof performance !== 'undefined' ? performance.now() : Date.now()) -
        startedTs,
    );
    return {
      ok: false,
      status: null,
      latencyMs,
      detail: controller.signal.aborted
        ? '请求超过 12 秒未完成'
        : err instanceof Error
          ? err.message
          : '请求失败',
      payload: null,
      checkedAt: new Date().toISOString(),
    };
  } finally {
    window.clearTimeout(timeout);
    pendingControllers.delete(controller);
  }
}

async function refreshAll(): Promise<void> {
  if (refreshing.value || disposed) return;
  refreshing.value = true;
  try {
    const [healthRes, readyRes, statsRes] = await Promise.all([
      probe('/health'),
      probe('/ready'),
      probe('/api/v1/market/stats'),
    ]);
    if (disposed) return;
    health.value = healthRes;
    ready.value = readyRes;
    statsProbe.value = statsRes;

    if (statsRes.ok && statsRes.payload) {
      stats.value = statsRes.payload as unknown as MarketStats;
    } else stats.value = null;

    // /health intentionally returns minimal info; /api/v1/admin/system carries
    // started_at / uptime, but it requires admin. We stay public-friendly here
    // and only show uptime if a public probe ever exposes it.
    const startedFromPayload = healthRes.payload?.['started_at'];
    if (typeof startedFromPayload === 'string') {
      startedAt.value = startedFromPayload;
    }
    const uptimeFromPayload = healthRes.payload?.['uptime_seconds'];
    if (typeof uptimeFromPayload === 'number') {
      uptimeSeconds.value = uptimeFromPayload;
    }

    lastRefreshedAt.value = new Date().toISOString();
  } finally {
    refreshing.value = false;
  }
}

const overall = computed<{
  tone: 'ok' | 'degraded' | 'down' | 'pending';
  label: string;
  description: string;
}>(() => {
  const probes = [health.value, ready.value, statsProbe.value];
  const known = probes.filter((p): p is ProbeResult => p !== null);
  if (known.length === 0) {
    return {
      tone: 'pending',
      label: '正在检查服务',
      description: '正在向后端核心接口发起健康检查。',
    };
  }
  const failed = known.filter((p) => !p.ok);
  if (failed.length === 0) {
    return {
      tone: 'ok',
      label: '三项服务检查均已通过',
      description: '核心接口可达，响应正常。',
    };
  }
  if (failed.length === known.length) {
    return {
      tone: 'down',
      label: '三项服务检查均未通过',
      description: '当前所有探测端点都未返回成功，请稍后重试或查看部署状态。',
    };
  }
  return {
    tone: 'degraded',
    label: '部分服务检查未通过',
    description: `${failed.length} / ${known.length} 个探测端点未通过，部分功能可能受影响。`,
  };
});

interface ProbeCard {
  key: 'health' | 'ready' | 'stats';
  title: string;
  subtitle: string;
  endpoint: string;
  result: ProbeResult | null;
}

const probes = computed<ProbeCard[]>(() => [
  {
    key: 'health',
    title: '进程存活',
    subtitle: '后端进程能否响应最基础的健康检查。',
    endpoint: 'GET /health',
    result: health.value,
  },
  {
    key: 'ready',
    title: '数据库就绪',
    subtitle: '后端是否完成数据库初始化并可以处理读请求。',
    endpoint: 'GET /ready',
    result: ready.value,
  },
  {
    key: 'stats',
    title: '市场公共接口',
    subtitle: '面向访客的市场数据接口可达性。',
    endpoint: 'GET /api/v1/market/stats',
    result: statsProbe.value,
  },
]);

const counters = computed(() => {
  const s = stats.value;
  if (!s) return [];
  return [
    { label: '已上架插件', value: s.published_plugins },
    { label: '插件总数', value: s.plugins_total },
    { label: '版本总数', value: s.versions_total },
    { label: '作者数量', value: s.authors_total },
    { label: '评分总数', value: s.ratings_total },
    { label: '订阅总数', value: s.likes_total },
    { label: '评论总数', value: s.comments_total },
    { label: '安装记录', value: s.downloads_total },
  ];
});

const uptimeText = computed(() => {
  if (uptimeSeconds.value !== null) {
    return formatUptime(uptimeSeconds.value);
  }
  if (startedAt.value) {
    const parsed = parseApiDate(startedAt.value);
    if (parsed) {
      return formatUptime(Math.max(0, (now.value - parsed.getTime()) / 1000));
    }
  }
  return null;
});

function relative(value: string | null | undefined): string {
  const parsed = parseApiDate(value);
  if (!parsed) return '—';
  const diff = Math.max(0, now.value - parsed.getTime());
  if (diff < 1000) return '刚刚';
  if (diff < 60000) return `${Math.floor(diff / 1000)} 秒前`;
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
  return parsed.toLocaleTimeString();
}

function probeTone(
  result: ProbeResult | null,
): 'ok' | 'degraded' | 'down' | 'pending' {
  if (!result) return 'pending';
  if (result.ok) return 'ok';
  if (result.status === null) return 'down';
  return 'degraded';
}

function probeLabel(result: ProbeResult | null): string {
  if (!result) return '检测中';
  if (result.ok) return '正常';
  if (result.status === null) return '不可达';
  return `异常 · ${result.status}`;
}

onMounted(() => {
  void refreshAll();
  if (typeof window !== 'undefined') {
    timer = window.setInterval(() => {
      void refreshAll();
    }, REFRESH_INTERVAL_MS);
    uptimeTimer = window.setInterval(() => {
      now.value = Date.now();
      if (uptimeSeconds.value !== null) {
        uptimeSeconds.value += 1;
      }
    }, 1000);
  }
});

onBeforeUnmount(() => {
  disposed = true;
  pendingControllers.forEach((controller) => controller.abort());
  pendingControllers.clear();
  if (timer !== null && typeof window !== 'undefined') {
    window.clearInterval(timer);
    timer = null;
  }
  if (uptimeTimer !== null && typeof window !== 'undefined') {
    window.clearInterval(uptimeTimer);
    uptimeTimer = null;
  }
});
</script>

<template>
  <div class="page-wrap status-page">
    <header class="status-hero" :data-tone="overall.tone">
      <div class="bulletin-imprint"><b>服务公报</b><span>公开监测 · 每 {{ REFRESH_INTERVAL_MS / 1000 }} 秒更新</span></div>
      <div class="status-hero-copy">
        <span class="status-kicker"><i aria-hidden="true"></i>{{ refreshing && lastRefreshedAt ? '上次检测 · 正在复查' : '本次检测' }}</span>
        <h1 aria-live="polite">{{ overall.label }}</h1>
        <p class="status-summary">{{ overall.description }}</p>
        <div class="status-meta">
          <span>最近更新：{{ relative(lastRefreshedAt) }}</span>
          <span v-if="uptimeText">运行时长：{{ uptimeText }}</span>
        </div>
      </div>
      <div class="status-hero-side">
        <span>通过的检查</span>
        <strong class="probe-tally">{{ lastRefreshedAt ? probes.filter(card => card.result?.ok).length : '—' }}<small> / {{ probes.length }}</small></strong>
        <button
          class="btn btn-sm"
          type="button"
          :disabled="refreshing"
          @click="refreshAll"
        >
          {{ refreshing ? '刷新中…' : '立即刷新' }}
        </button>
      </div>
    </header>

    <section class="status-section">
      <div class="section-head compact-head">
        <h2><span class="section-number">01</span> 核心服务</h2>
        <p>对外可访问的关键接口实时探测结果。</p>
      </div>
      <div class="probe-grid">
        <article
          v-for="card in probes"
          :key="card.key"
          class="probe-card"
          :data-tone="probeTone(card.result)"
        >
          <header class="probe-card-head">
            <div>
              <h3>{{ card.title }}</h3>
              <p>{{ card.subtitle }}</p>
            </div>
            <span class="probe-status">
              <span class="status-dot" />
              {{ probeLabel(card.result) }}
            </span>
          </header>
          <dl class="probe-card-body">
            <div>
              <dt>端点</dt>
              <dd>
                <code>{{ card.endpoint }}</code>
              </dd>
            </div>
            <div>
              <dt>HTTP</dt>
              <dd>{{ card.result?.status ?? '—' }}</dd>
            </div>
            <div>
              <dt>响应时延</dt>
              <dd>
                {{
                  card.result?.latencyMs !== null &&
                  card.result?.latencyMs !== undefined
                    ? `${card.result.latencyMs} ms`
                    : '—'
                }}
              </dd>
            </div>
            <div>
              <dt>最近探测</dt>
              <dd>{{ relative(card.result?.checkedAt) }}</dd>
            </div>
          </dl>
          <p v-if="card.result && !card.result.ok" class="probe-detail">
            {{ card.result.detail || '请求失败' }}
          </p>
        </article>
      </div>
    </section>

    <section class="status-section">
      <div class="section-head compact-head">
        <h2><span class="section-number">02</span> 市场数据</h2>
        <p>当前公开的市场规模与社区参与情况。</p>
      </div>
      <div v-if="counters.length" class="counter-grid">
        <div v-for="item in counters" :key="item.label" class="counter-card">
          <span class="counter-label">{{ item.label }}</span>
          <strong class="counter-value">{{ typeof item.value === 'number' ? formatNumber(item.value) : '—' }}</strong>
        </div>
      </div>
      <p v-else-if="!statsProbe" class="stats-pending" role="status">等候本次市场数据检查。</p>
      <p v-else class="probe-detail">暂未获取到市场统计数据，请稍后再试。</p>
    </section>

    <section class="status-section status-tips">
      <div class="section-head compact-head">
        <h2><span class="section-number">03</span> 需要帮助</h2>
        <p>如果状态长期处于异常或降级，可以尝试以下操作。</p>
      </div>
      <ul class="tip-list">
        <li>刷新页面或稍后再试，瞬时网络抖动可能造成单次探测失败。</li>
        <li>记录未通过的端点、HTTP 状态和最近探测时间，反馈问题时一并提供。</li>
        <li>
          到 GitHub 仓库
          <a
            href="https://github.com/MoFox-Studio"
            target="_blank"
            rel="noreferrer noopener"
            >MoFox-Studio</a
          >
          反馈持续不可用的问题。
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.status-page {
  display: grid;
  gap: 36px;
}
.status-hero {
  display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 22px 36px;
  align-items: end; padding-bottom: 26px; border-bottom: 3px double var(--ink-700);
}
.bulletin-imprint {
  grid-column: 1/-1; display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 9px 0; border-top: 2px solid var(--ink-900); border-bottom: 1px solid var(--line-strong);
  font-size: 11px; letter-spacing: .08em;
}
.bulletin-imprint b { color: var(--blue-700); }
.status-hero-copy { padding: 6px 0; }
.status-kicker { display: flex; align-items: center; gap: 10px; font-size: 13px; color: var(--ink-700); }
.status-kicker i { width: 9px; height: 9px; background: var(--ink-500); }
.status-hero[data-tone='ok'] .status-kicker i { background: var(--success-ink); }
.status-hero[data-tone='degraded'] .status-kicker i { background: var(--warning-ink); }
.status-hero[data-tone='down'] .status-kicker i { background: var(--danger-ink); }
.status-hero h1 { margin: 14px 0; font: 800 clamp(35px, 4.7vw, 65px)/1.25 var(--font-editorial); letter-spacing: -.05em; text-wrap: balance; }
.status-summary { margin: 0; color: var(--ink-700); line-height: 1.85; }
.status-meta { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 16px; color: var(--ink-500); font: 11px var(--font-mono); }
.status-hero-side { align-self: stretch; display: grid; justify-items: start; align-content: center; gap: 7px; padding-left: 24px; border-left: 1px solid var(--line-strong); }
.status-hero-side > span { color: var(--ink-500); font-size: 12px; }
.probe-tally { font: 800 48px/1.15 var(--font-editorial); color: var(--blue-700); }
.probe-tally small { color: var(--ink-500); font: 16px var(--font-mono); }
.status-hero-side .btn { margin-top: 8px; }
.stats-pending { margin: 0; color: var(--ink-500); padding: 18px 0; border-top: 1px solid var(--line); }
.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}
.status-section {
  display: grid;
  gap: 20px;
}
.section-head.compact-head {
  display: grid;
  gap: 7px;
  margin: 0;
}
.section-head h2 {
  font-size: 18px;
  margin: 0;
}
.section-head p {
  margin: 0;
  font-size: 13px;
  color: var(--ink-500);
}
.section-number {
  font: 11px var(--font-mono);
  color: var(--blue-600);
  margin-right: 9px;
}
.probe-grid { display: grid; border-top: 2px solid var(--ink-700); }
.probe-card {
  display: grid; grid-template-columns: minmax(215px, 1fr) minmax(0, 2fr); gap: 14px 30px;
  padding: 19px 20px; border-bottom: 1px solid var(--line); background: var(--surface); min-width: 0;
}
.probe-card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.probe-card .probe-card-body { grid-template-columns: minmax(100px, 1.5fr) repeat(3,minmax(0,1fr)); align-self: center; }
.probe-card .probe-detail { grid-column: 1/-1; margin: 0; }
.probe-card-head h3 {
  font-size: 15px;
  margin: 0 0 7px;
}
.probe-card-head p {
  font-size: 11px;
  line-height: 1.7;
  margin: 0;
  color: var(--ink-500);
}
.probe-status {
  display: flex;
  gap: 6px;
  align-items: center;
  white-space: nowrap;
  font-size: 11px;
  color: var(--ink-500);
}
.probe-card[data-tone='ok'] .probe-status {
  color: var(--success-ink);
}
.probe-card[data-tone='down'] .probe-status,
.probe-card[data-tone='degraded'] .probe-status {
  color: var(--danger-ink);
}
.probe-card-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px 12px;
  margin: 0;
}
.probe-card-body dt {
  font-size: 10px;
  color: var(--ink-500);
  margin-bottom: 7px;
}
.probe-card-body dd {
  margin: 0;
  font: 12px var(--font-mono);
  overflow-wrap: anywhere;
}
.probe-card-body code {
  font-size: 10px;
  background: transparent;
  padding: 0;
}
.probe-detail {
  background: var(--danger-soft);
  color: var(--danger-ink);
  font-size: 12px;
  padding: 14px;
  line-height: 1.7;
  overflow-wrap: anywhere;
  margin: 16px 0 0;
}
.counter-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
}
.counter-card {
  display: flex;
  flex-direction: column;
  gap: 18px;
  background: var(--surface);
  padding: 24px;
}
.counter-label {
  color: var(--ink-500);
  font-size: 11px;
}
.counter-value {
  font: 30px/1 var(--font-mono);
  letter-spacing: -0.06em;
}
.status-tips {
  border-top: 1px solid var(--line);
  padding-top: 28px;
}
.tip-list {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  line-height: 1.9;
  color: var(--ink-500);
}
.tip-list a {
  color: var(--blue-600);
  text-decoration: underline;
}
@media (max-width: 930px) {
  .probe-card { grid-template-columns: 1fr; }
  .status-hero { gap: 18px; }
}
@media (max-width: 620px) {
  .status-hero { grid-template-columns: 1fr; }
  .status-hero-side { border-left: 0; border-top: 1px solid var(--line); padding: 14px 0 0; display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }
  .status-hero-side .btn { margin: 0 0 0 auto; }
  .probe-tally { font-size: 30px; }
  .probe-card { padding: 16px; }
  .probe-card .probe-card-body, .counter-grid { grid-template-columns: 1fr 1fr; }
  .counter-card { padding: 18px; }
}
</style>
