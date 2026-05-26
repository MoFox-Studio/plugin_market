<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { MarketStats } from '@/types'
import { formatNumber, formatUptime, parseApiDate } from '@/utils/format'

interface ProbeResult {
  ok: boolean
  status: number | null
  latencyMs: number | null
  detail: string | null
  payload: Record<string, unknown> | null
  checkedAt: string | null
}

const REFRESH_INTERVAL_MS = 30000

const health = ref<ProbeResult | null>(null)
const ready = ref<ProbeResult | null>(null)
const statsProbe = ref<ProbeResult | null>(null)

const stats = ref<MarketStats | null>(null)
const startedAt = ref<string | null>(null)
const uptimeSeconds = ref<number | null>(null)
const lastRefreshedAt = ref<string | null>(null)
const refreshing = ref(false)
let timer: number | null = null
let uptimeTimer: number | null = null

async function probe(path: string): Promise<ProbeResult> {
  const startedTs = (typeof performance !== 'undefined' ? performance.now() : Date.now())
  try {
    const response = await fetch(path, { credentials: 'include' })
    const latencyMs = Math.round((typeof performance !== 'undefined' ? performance.now() : Date.now()) - startedTs)
    let payload: Record<string, unknown> | null = null
    try {
      payload = await response.clone().json()
    } catch {
      payload = null
    }
    return {
      ok: response.ok,
      status: response.status,
      latencyMs,
      detail: response.ok ? null : (response.statusText || `HTTP ${response.status}`),
      payload,
      checkedAt: new Date().toISOString(),
    }
  } catch (err) {
    const latencyMs = Math.round((typeof performance !== 'undefined' ? performance.now() : Date.now()) - startedTs)
    return {
      ok: false,
      status: null,
      latencyMs,
      detail: err instanceof Error ? err.message : '请求失败',
      payload: null,
      checkedAt: new Date().toISOString(),
    }
  }
}

async function refreshAll(): Promise<void> {
  if (refreshing.value) return
  refreshing.value = true
  try {
    const [healthRes, readyRes, statsRes] = await Promise.all([
      probe('/health'),
      probe('/ready'),
      probe('/api/v1/market/stats'),
    ])
    health.value = healthRes
    ready.value = readyRes
    statsProbe.value = statsRes

    if (statsRes.ok && statsRes.payload) {
      stats.value = statsRes.payload as unknown as MarketStats
    }

    // /health intentionally returns minimal info; /api/v1/admin/system carries
    // started_at / uptime, but it requires admin. We stay public-friendly here
    // and only show uptime if a public probe ever exposes it.
    const startedFromPayload = healthRes.payload?.['started_at']
    if (typeof startedFromPayload === 'string') {
      startedAt.value = startedFromPayload
    }
    const uptimeFromPayload = healthRes.payload?.['uptime_seconds']
    if (typeof uptimeFromPayload === 'number') {
      uptimeSeconds.value = uptimeFromPayload
    }

    lastRefreshedAt.value = new Date().toISOString()
  } finally {
    refreshing.value = false
  }
}

const overall = computed<{ tone: 'ok' | 'degraded' | 'down'; label: string; description: string }>(() => {
  const probes = [health.value, ready.value, statsProbe.value]
  const known = probes.filter((p): p is ProbeResult => p !== null)
  if (known.length === 0) {
    return { tone: 'degraded', label: '正在检测', description: '正在向后端核心接口发起健康检查。' }
  }
  const failed = known.filter((p) => !p.ok)
  if (failed.length === 0) {
    return {
      tone: 'ok',
      label: '一切正常',
      description: '核心接口可达，响应正常。',
    }
  }
  if (failed.length === known.length) {
    return {
      tone: 'down',
      label: '服务不可用',
      description: '当前所有探测端点都未返回成功，请稍后重试或查看部署状态。',
    }
  }
  return {
    tone: 'degraded',
    label: '部分降级',
    description: `${failed.length} / ${known.length} 个探测端点未通过，部分功能可能受影响。`,
  }
})

interface ProbeCard {
  key: 'health' | 'ready' | 'stats'
  title: string
  subtitle: string
  endpoint: string
  result: ProbeResult | null
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
])

const counters = computed(() => {
  const s = stats.value
  if (!s) return []
  return [
    { label: '已上架插件', value: s.published_plugins ?? s.plugins_total ?? 0 },
    { label: '插件总数', value: s.plugins_total ?? 0 },
    { label: '版本总数', value: s.versions_total ?? 0 },
    { label: '作者数量', value: s.authors_total ?? 0 },
    { label: '评分总数', value: s.ratings_total ?? 0 },
    { label: '点赞总数', value: s.likes_total ?? 0 },
    { label: '评论总数', value: s.comments_total ?? 0 },
    { label: '安装记录', value: s.downloads_total ?? 0 },
  ]
})

const uptimeText = computed(() => {
  if (uptimeSeconds.value !== null) {
    return formatUptime(uptimeSeconds.value)
  }
  if (startedAt.value) {
    const parsed = parseApiDate(startedAt.value)
    if (parsed) {
      return formatUptime(Math.max(0, (Date.now() - parsed.getTime()) / 1000))
    }
  }
  return null
})

function relative(value: string | null | undefined): string {
  const parsed = parseApiDate(value)
  if (!parsed) return '—'
  const diff = Math.max(0, Date.now() - parsed.getTime())
  if (diff < 1000) return '刚刚'
  if (diff < 60000) return `${Math.floor(diff / 1000)} 秒前`
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  return parsed.toLocaleTimeString()
}

function probeTone(result: ProbeResult | null): 'ok' | 'degraded' | 'down' | 'pending' {
  if (!result) return 'pending'
  if (result.ok) return 'ok'
  if (result.status === null) return 'down'
  return 'degraded'
}

function probeLabel(result: ProbeResult | null): string {
  if (!result) return '检测中'
  if (result.ok) return '正常'
  if (result.status === null) return '不可达'
  return `异常 · ${result.status}`
}

onMounted(() => {
  void refreshAll()
  if (typeof window !== 'undefined') {
    timer = window.setInterval(() => {
      void refreshAll()
    }, REFRESH_INTERVAL_MS)
    uptimeTimer = window.setInterval(() => {
      if (uptimeSeconds.value !== null) {
        uptimeSeconds.value += 1
      }
    }, 1000)
  }
})

onBeforeUnmount(() => {
  if (timer !== null && typeof window !== 'undefined') {
    window.clearInterval(timer)
    timer = null
  }
  if (uptimeTimer !== null && typeof window !== 'undefined') {
    window.clearInterval(uptimeTimer)
    uptimeTimer = null
  }
})
</script>

<template>
  <div class="status-page">
    <header class="status-hero" :data-tone="overall.tone">
      <div class="status-hero-copy">
        <span class="status-kicker">Service Status</span>
        <h1>服务状态</h1>
        <p class="status-summary">{{ overall.description }}</p>
        <div class="status-meta">
          <span>最近更新：{{ relative(lastRefreshedAt) }}</span>
          <span v-if="uptimeText">运行时长：{{ uptimeText }}</span>
          <span>每 {{ REFRESH_INTERVAL_MS / 1000 }}s 自动刷新</span>
        </div>
      </div>
      <div class="status-hero-side">
        <div class="status-pill" :data-tone="overall.tone">
          <span class="status-dot" />
          <strong>{{ overall.label }}</strong>
        </div>
        <button
          class="btn btn-sm"
          type="button"
          :disabled="refreshing"
          @click="refreshAll"
        >{{ refreshing ? '刷新中…' : '立即刷新' }}</button>
      </div>
    </header>

    <section class="status-section">
      <div class="section-head compact-head">
        <h2>核心探测</h2>
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
              <dd><code>{{ card.endpoint }}</code></dd>
            </div>
            <div>
              <dt>HTTP</dt>
              <dd>{{ card.result?.status ?? '—' }}</dd>
            </div>
            <div>
              <dt>响应时延</dt>
              <dd>{{ card.result?.latencyMs !== null && card.result?.latencyMs !== undefined ? `${card.result.latencyMs} ms` : '—' }}</dd>
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
        <h2>市场数据</h2>
        <p>来自 <code>/api/v1/market/stats</code> 的公共统计指标。</p>
      </div>
      <div v-if="counters.length" class="counter-grid">
        <div v-for="item in counters" :key="item.label" class="counter-card">
          <span class="counter-label">{{ item.label }}</span>
          <strong class="counter-value">{{ formatNumber(item.value) }}</strong>
        </div>
      </div>
      <p v-else class="probe-detail">暂未获取到市场统计数据，请稍后再试。</p>
    </section>

    <section class="status-section status-tips">
      <div class="section-head compact-head">
        <h2>遇到问题？</h2>
        <p>如果状态长期处于异常或降级，可以尝试以下操作。</p>
      </div>
      <ul class="tip-list">
        <li>刷新页面或稍后再试，瞬时网络抖动可能造成单次探测失败。</li>
        <li>检查浏览器是否因登录态失效而被拦截，必要时重新登录。</li>
        <li>到 GitHub 仓库 <a href="https://github.com/MoFox-Studio" target="_blank" rel="noreferrer noopener">MoFox-Studio</a> 反馈持续不可用的问题。</li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.status-page {
  width: min(var(--shell-max), 100%);
  margin: 0 auto;
  padding: var(--space-7) var(--space-7) var(--space-16);
  display: grid;
  gap: var(--space-7);
}
@media (max-width: 768px) {
  .status-page { padding: var(--space-5) var(--space-4) var(--space-12); }
}

.status-hero {
  position: relative;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--space-6);
  align-items: center;
  padding: var(--space-7);
  border-radius: var(--radius-lg);
  border: 1.5px solid var(--line);
  background: var(--surface);
  box-shadow: var(--shadow-2);
  overflow: hidden;
}
.status-hero::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: .25;
  background: var(--halftone);
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, .85), transparent 80%);
}
.status-hero[data-tone="ok"] { background: linear-gradient(135deg, var(--success-soft), var(--surface) 70%); }
.status-hero[data-tone="degraded"] { background: linear-gradient(135deg, var(--warning-soft), var(--surface) 70%); }
.status-hero[data-tone="down"] { background: linear-gradient(135deg, var(--danger-soft), var(--surface) 70%); }

.status-hero-copy {
  position: relative;
  z-index: 1;
  display: grid;
  gap: var(--space-2);
}
.status-kicker {
  font-family: var(--font-brand);
  letter-spacing: var(--letter-kicker);
  text-transform: uppercase;
  font-size: var(--fs-sm);
  color: var(--ink-500);
}
.status-hero h1 {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--fs-display-2);
  line-height: var(--lh-tight);
  font-weight: 900;
  color: var(--ink-900);
}
.status-summary { margin: 0; color: var(--ink-700); font-size: var(--fs-lg); max-width: 56ch; }
.status-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  color: var(--ink-500);
  font-size: var(--fs-sm);
  margin-top: var(--space-2);
}
.status-meta span { display: inline-flex; align-items: center; gap: 6px; }

.status-hero-side {
  position: relative;
  z-index: 1;
  display: grid;
  gap: var(--space-3);
  justify-items: end;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: var(--radius-pill);
  border: 1.5px solid currentColor;
  background: var(--surface);
  font-size: var(--fs-sm);
  font-weight: 700;
}
.status-pill[data-tone="ok"] { color: var(--success-ink); background: var(--success-soft); }
.status-pill[data-tone="degraded"] { color: var(--warning-ink); background: var(--warning-soft); }
.status-pill[data-tone="down"] { color: var(--danger-ink); background: var(--danger-soft); }
.status-pill strong { font-family: var(--font-display); }

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 25%, transparent);
}

@media (max-width: 720px) {
  .status-hero { grid-template-columns: 1fr; }
  .status-hero-side { justify-items: start; }
}

.status-section { display: grid; gap: var(--space-4); }
.status-section .section-head.compact-head { display: grid; gap: 4px; }

.probe-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--space-4);
}

.probe-card {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-5);
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-1);
}
.probe-card[data-tone="ok"] { border-color: color-mix(in srgb, var(--success) 40%, var(--line)); }
.probe-card[data-tone="degraded"] { border-color: color-mix(in srgb, var(--warning) 50%, var(--line)); }
.probe-card[data-tone="down"] { border-color: color-mix(in srgb, var(--danger) 50%, var(--line)); }

.probe-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}
.probe-card-head h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--fs-h3);
  font-weight: 800;
  color: var(--ink-900);
}
.probe-card-head p {
  margin: 4px 0 0;
  color: var(--ink-500);
  font-size: var(--fs-sm);
  line-height: var(--lh-snug);
}

.probe-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-pill);
  font-size: var(--fs-xs);
  font-weight: 700;
  white-space: nowrap;
  background: var(--surface-soft);
  color: var(--ink-500);
}
.probe-card[data-tone="ok"] .probe-status { background: var(--success-soft); color: var(--success-ink); }
.probe-card[data-tone="degraded"] .probe-status { background: var(--warning-soft); color: var(--warning-ink); }
.probe-card[data-tone="down"] .probe-status { background: var(--danger-soft); color: var(--danger-ink); }
.probe-card[data-tone="pending"] .probe-status { background: var(--surface-soft); color: var(--ink-500); }

.probe-card-body {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
  margin: 0;
}
.probe-card-body div { display: grid; gap: 2px; }
.probe-card-body dt {
  font-size: var(--fs-mini);
  text-transform: uppercase;
  letter-spacing: var(--letter-wide);
  color: var(--ink-500);
}
.probe-card-body dd {
  margin: 0;
  font-size: var(--fs-base);
  font-weight: 600;
  color: var(--ink-900);
  word-break: break-all;
}
.probe-card-body code {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  background: var(--surface-soft);
  padding: 2px 6px;
  border-radius: var(--radius-xs);
}

.probe-detail {
  margin: 0;
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--danger-soft);
  color: var(--danger-ink);
  font-size: var(--fs-sm);
}

.counter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: var(--space-3);
}
.counter-card {
  display: grid;
  gap: 6px;
  padding: var(--space-4) var(--space-5);
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-1);
}
.counter-label {
  font-size: var(--fs-mini);
  text-transform: uppercase;
  letter-spacing: var(--letter-wide);
  color: var(--ink-500);
}
.counter-value {
  font-family: var(--font-display);
  font-size: 28px;
  line-height: var(--lh-tight);
  font-weight: 900;
  color: var(--ink-900);
}

.status-tips .tip-list {
  margin: 0;
  padding-left: 1.2em;
  display: grid;
  gap: 6px;
  color: var(--ink-700);
  font-size: var(--fs-base);
  line-height: var(--lh-base);
}
.status-tips a { color: var(--blue-700); text-decoration: underline; }
</style>
