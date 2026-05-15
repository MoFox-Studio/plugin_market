<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { formatNumber, formatRelative, formatDate, formatBytes, formatUptime, statusText, trustLevelLabel, reviewActionText } from '@/utils/format'
import type { Plugin, PluginSnapshot, SystemInfo, DashboardData, ReviewItem, ActivityDay } from '@/types'
import TrustBadge from '@/components/TrustBadge.vue'
import EmptyState from '@/components/EmptyState.vue'

const auth = useAuthStore()
const toast = useToastStore()

const system = ref<SystemInfo | null>(null)
const dashboard = ref<DashboardData | null>(null)
const plugins = ref<Plugin[]>([])
const reviews = ref<ReviewItem[]>([])
const selectedId = ref<string | null>(null)
const snapshot = ref<PluginSnapshot | null>(null)
const selectedPlugin = ref<Plugin | null>(null)
const loading = ref(true)

async function loadAll() {
  loading.value = true
  const [sys, dash, pluginResult, reviewResult] = await Promise.all([
    api.get('/api/v1/admin/system'),
    api.get('/api/v1/admin/dashboard'),
    api.get('/api/v1/admin/plugins'),
    api.get('/api/v1/admin/reviews'),
  ])
  system.value = sys
  dashboard.value = dash
  plugins.value = pluginResult.items || []
  reviews.value = reviewResult || []

  // Auto-select first pending or first plugin
  if (!selectedId.value && plugins.value.length) {
    const pending = plugins.value.find(p => p.status === 'pending_review')
    selectedId.value = pending ? pending.plugin_id : plugins.value[0].plugin_id
  }
  if (selectedId.value) await loadSnapshot()
  loading.value = false
}

async function loadSnapshot() {
  if (!selectedId.value) { snapshot.value = null; selectedPlugin.value = null; return }
  const s = await api.get(`/api/v1/admin/plugins/${encodeURIComponent(selectedId.value)}`).catch(() => null)
  snapshot.value = s
  selectedPlugin.value = s?.plugin || null
}

async function selectPlugin(id: string) {
  selectedId.value = id
  await loadSnapshot()
}

async function pluginAction(action: string, pluginId: string) {
  if (!confirm(`确认执行 ${action} 操作：${pluginId} ？`)) return
  const reason = action === 'delete' ? '' : (prompt('可填写操作原因，留空也可以。', '') || '')
  try {
    if (action === 'delete') {
      await api.del(`/api/v1/admin/plugins/${encodeURIComponent(pluginId)}`)
      if (selectedId.value === pluginId) { selectedId.value = null; snapshot.value = null; selectedPlugin.value = null }
    } else {
      await api.post(`/api/v1/admin/plugins/${encodeURIComponent(pluginId)}/${action}`, reason.trim() ? { reason: reason.trim() } : {})
    }
    toast.show(action === 'delete' ? '插件已删除' : '治理动作已执行', 'ok')
    await loadAll()
  } catch (e) {
    toast.show((e as Error).message || '操作失败', 'error')
  }
}

async function setTrustLevel(pluginId: string, level: string) {
  if (selectedPlugin.value?.trust_level === level) return
  const reason = prompt(`可填写切换为"${trustLevelLabel(level)}"的原因，留空也可以。`, '') || ''
  try {
    await api.post(`/api/v1/admin/plugins/${encodeURIComponent(pluginId)}/trust-level/${encodeURIComponent(level)}`, reason.trim() ? { reason: reason.trim() } : {})
    toast.show('社区标识已更新', 'ok')
    await loadSnapshot()
  } catch (e) {
    toast.show((e as Error).message || '切换失败', 'error')
  }
}

async function versionAction(action: string, pluginId: string, version: string) {
  if (!confirm(`确认对 ${pluginId}@${version} 执行 ${action} 吗？`)) return
  const reason = prompt('可填写操作原因，留空也可以。', '') || ''
  try {
    await api.post(`/api/v1/admin/plugins/${encodeURIComponent(pluginId)}/versions/${encodeURIComponent(version)}/${action}`, reason.trim() ? { reason: reason.trim() } : {})
    toast.show('版本治理动作已执行', 'ok')
    await loadSnapshot()
  } catch (e) {
    toast.show((e as Error).message || '操作失败', 'error')
  }
}

// Activity chart helpers
function activityBarHeight(value: number, max: number) {
  return Math.max(8, Math.round((value || 0) / Math.max(1, max) * 88)) + 'px'
}

function activityMax(activity: ActivityDay[]) {
  const peaks = (activity || []).flatMap(d => [d.plugins_created, d.comments_created, d.ratings_created])
  return Math.max(1, ...peaks)
}

onMounted(loadAll)
</script>

<template>
  <!-- Not admin -->
  <div v-if="!auth.isAdmin" style="padding-top:40px">
    <EmptyState title="需要管理员权限" message="请使用具有管理员权限的 GitHub 账号登录。" />
  </div>

  <!-- Loading -->
  <div v-else-if="loading" class="loading-screen">加载中…</div>

  <!-- Admin panel -->
  <div v-else class="control-room">
    <div class="admin-shell">
      <!-- Sidebar nav -->
      <aside class="panel admin-page-sidebar">
        <div class="admin-page-sidebar-head">
          <span class="control-kicker">Admin Nav</span>
          <h2>快速切换</h2>
          <p>直接跳到你现在要处理的那一块，不用整页下滑。</p>
        </div>
        <nav class="admin-nav" aria-label="管理后台分区导航">
          <a class="admin-nav-link" href="#admin-overview">总览</a>
          <a class="admin-nav-link" href="#admin-queue">治理队列</a>
          <a class="admin-nav-link" href="#admin-plugin-governance">插件治理</a>
          <a class="admin-nav-link" href="#admin-version-governance">版本治理</a>
          <a class="admin-nav-link" href="#admin-trends">趋势观察</a>
          <a class="admin-nav-link" href="#admin-review-feed">审核流</a>
          <a class="admin-nav-link" href="#admin-plugin-history">治理历史</a>
        </nav>
      </aside>

      <!-- Main content -->
      <div class="admin-page-content">
        <!-- Overview hero -->
        <section v-if="system" class="control-hero admin-hero" id="admin-overview">
          <div class="control-hero-copy">
            <span class="control-kicker">Moderation Room</span>
            <h1>插件市场后端管理台</h1>
            <p>在这里进行状态治理、服务监控和社区节奏追踪，方便你判断市场的实时动态。</p>
            <div class="control-pills">
              <span class="control-pill">{{ system.environment }}</span>
              <span class="control-pill">运行 {{ formatUptime(system.uptime_seconds) }}</span>
              <span class="control-pill">OAuth {{ system.github_oauth_configured ? '已接通' : '未配置' }}</span>
              <span class="control-pill">Webhook {{ system.github_webhook_configured ? '在线' : '未配置' }}</span>
            </div>
          </div>
          <div class="server-stack">
            <div class="server-tile"><span>服务状态</span><strong>{{ system.status }}</strong><small>数据库 {{ system.database }}</small></div>
            <div class="server-tile"><span>审核模式</span><strong>{{ system.review_required ? '人工审核' : '快速发布' }}</strong><small>最近审核 {{ formatRelative(system.stats.latest_review_at) }}</small></div>
            <div class="server-tile"><span>数据库路径</span><strong>{{ system.database_path || '内存数据库' }}</strong><small>启动于 {{ formatDate(system.started_at) }}</small></div>
          </div>
        </section>

        <!-- Metrics -->
        <section v-if="dashboard" class="control-metrics-row admin-metrics">
          <div class="control-metric"><span>插件总数</span><b>{{ dashboard.stats.plugins_total }}</b><small>{{ dashboard.stats.pending_plugins }} 待审核</small></div>
          <div class="control-metric"><span>版本总数</span><b>{{ dashboard.stats.versions_total }}</b><small>{{ dashboard.stats.pending_versions }} 待审核</small></div>
          <div class="control-metric"><span>评论 / 评分</span><b>{{ formatNumber(dashboard.stats.comments_total) }} / {{ formatNumber(dashboard.stats.ratings_total) }}</b><small>社区互动</small></div>
          <div class="control-metric"><span>点赞 / 下载</span><b>{{ formatNumber(dashboard.stats.likes_total) }} / {{ formatNumber(dashboard.stats.downloads_total) }}</b><small>热度追踪</small></div>
          <div class="control-metric"><span>作者 / Webhook</span><b>{{ dashboard.stats.authors_total }} / {{ dashboard.stats.webhooks_total }}</b><small>生态节点</small></div>
        </section>

        <!-- Activity + Queue -->
        <section v-if="dashboard" class="admin-board">
          <div class="panel activity-panel">
            <div class="section-head compact-head"><div><h2>最近 7 天市场动态</h2><p>重点观察新增插件、评论和评分的波动。</p></div></div>
            <!-- Activity chart -->
            <div class="activity-legend">
              <span><i class="dot dot-plugin"></i>新增插件</span>
              <span><i class="dot dot-comment"></i>评论</span>
              <span><i class="dot dot-rating"></i>评分</span>
            </div>
            <div class="activity-chart">
              <div v-for="day in (dashboard.activity || [])" :key="day.date" class="activity-day">
                <div class="activity-bars">
                  <span class="activity-bar plugin" :style="{ height: activityBarHeight(day.plugins_created, activityMax(dashboard.activity || [])) }" :title="`新增插件 ${day.plugins_created || 0}`"></span>
                  <span class="activity-bar comment" :style="{ height: activityBarHeight(day.comments_created, activityMax(dashboard.activity || [])) }" :title="`评论 ${day.comments_created || 0}`"></span>
                  <span class="activity-bar rating" :style="{ height: activityBarHeight(day.ratings_created, activityMax(dashboard.activity || [])) }" :title="`评分 ${day.ratings_created || 0}`"></span>
                </div>
                <strong>{{ day.date ? day.date.slice(5) : '--' }}</strong>
                <small>{{ (day.plugins_created || 0) + (day.comments_created || 0) + (day.ratings_created || 0) }} 动态</small>
              </div>
            </div>
            <!-- Breakdowns -->
            <div class="breakdown-row">
              <div class="mini-breakdown">
                <h4>插件状态分布</h4>
                <div class="mini-breakdown-grid">
                  <div v-for="[key, value] in Object.entries(dashboard.plugin_status_breakdown || {}).filter(([,v]) => v > 0)" :key="key" class="mini-breakdown-item">
                    <span>{{ statusText(key) }}</span>
                    <b>{{ value }}</b>
                  </div>
                </div>
              </div>
              <div class="mini-breakdown">
                <h4>版本状态分布</h4>
                <div class="mini-breakdown-grid">
                  <div v-for="[key, value] in Object.entries(dashboard.version_status_breakdown || {}).filter(([,v]) => v > 0)" :key="key" class="mini-breakdown-item">
                    <span>{{ statusText(key) }}</span>
                    <b>{{ value }}</b>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Queue -->
          <div class="panel queue-panel" id="admin-queue">
            <div class="section-head compact-head"><div><h2>治理队列</h2><p>优先处理待审核与异常插件。点击条目切换右侧详情。</p></div></div>
            <div v-if="plugins.length" class="control-list">
              <button
                v-for="p in plugins"
                :key="p.plugin_id"
                type="button"
                :class="['control-list-item', { 'is-active': p.plugin_id === selectedId }]"
                @click="selectPlugin(p.plugin_id)"
              >
                <div>
                  <strong>{{ p.display_name }}</strong>
                  <span>{{ p.plugin_id }}</span>
                </div>
                <div>
                  <span :class="['badge', `status-${p.status}`]">{{ statusText(p.status) }}</span>
                  <small>{{ formatRelative(p.updated_at) }}</small>
                </div>
              </button>
            </div>
            <EmptyState v-else title="暂无插件" message="当前市场没有插件记录。" />
          </div>
        </section>

        <!-- Plugin governance -->
        <section class="ops-grid">
          <div class="panel plugin-sheet" id="admin-plugin-governance">
            <template v-if="selectedPlugin">
              <div class="section-head compact-head">
                <div><h2>{{ selectedPlugin.display_name }}</h2><p>{{ selectedPlugin.summary }}</p></div>
                <div class="table-actions">
                  <TrustBadge :level="selectedPlugin.trust_level" />
                  <span :class="['badge', `status-${selectedPlugin.status}`]">{{ statusText(selectedPlugin.status) }}</span>
                </div>
              </div>
              <div class="plugin-sheet-grid">
                <div>
                  <h4>治理动作</h4>
                  <p class="soft-note">支持退回、封禁、下架、删除，以及在修复后重新上架。</p>
                  <div class="table-actions admin-action-cluster">
                    <button v-if="selectedPlugin.status !== 'published'" class="btn btn-sm" @click="pluginAction('publish', selectedPlugin.plugin_id)">重新上架</button>
                    <button v-if="selectedPlugin.status !== 'draft'" class="btn btn-sm" @click="pluginAction('reject', selectedPlugin.plugin_id)">退回</button>
                    <button v-if="selectedPlugin.status !== 'deprecated'" class="btn btn-sm" @click="pluginAction('deprecate', selectedPlugin.plugin_id)">下架</button>
                    <button v-if="selectedPlugin.status !== 'blocked'" class="btn btn-sm btn-danger" @click="pluginAction('block', selectedPlugin.plugin_id)">封禁</button>
                    <button class="btn btn-sm btn-danger" @click="pluginAction('delete', selectedPlugin.plugin_id)">删除</button>
                  </div>
                  <h4 style="margin-top:18px">社区标识</h4>
                  <p class="soft-note">直接切换插件在市场中显示的身份标签，用于区分官方、认证和普通社区作品。</p>
                  <div class="table-actions trust-switch-row">
                    <button
                      v-for="level in ['official', 'verified', 'community']"
                      :key="level"
                      :class="['btn', 'btn-sm', { 'is-active': selectedPlugin.trust_level === level }]"
                      @click="setTrustLevel(selectedPlugin.plugin_id, level)"
                    >{{ trustLevelLabel(level) }}</button>
                  </div>
                </div>
                <div>
                  <h4>社区状态</h4>
                  <ul class="meta-list">
                    <li><span>作者</span><strong>{{ selectedPlugin.owner_display_name || selectedPlugin.owner_login || selectedPlugin.owner_id }}</strong></li>
                    <li><span>当前标识</span><strong>{{ trustLevelLabel(selectedPlugin.trust_level) }}</strong></li>
                    <li><span>评分</span><strong>{{ selectedPlugin.rating_avg.toFixed(1) }} / {{ selectedPlugin.rating_count }}</strong></li>
                    <li><span>互动</span><strong>{{ formatNumber(selectedPlugin.comments_count) }} 评论 · {{ formatNumber(selectedPlugin.likes_count) }} 点赞</strong></li>
                    <li><span>流量</span><strong>{{ formatNumber(selectedPlugin.downloads_count) }} 下载</strong></li>
                  </ul>
                </div>
              </div>
            </template>
            <EmptyState v-else title="未选择插件" message="从左侧队列里点一个插件，即可查看完整治理面板。" />
          </div>

          <!-- Version governance -->
          <div class="panel version-governance" id="admin-version-governance">
            <div class="section-head compact-head"><div><h2>版本治理</h2><p>支持恢复、退回、下架与封禁版本。</p></div></div>
            <template v-if="selectedPlugin">
              <div v-if="(snapshot?.versions || []).length" class="governance-version-list">
                <div v-for="v in snapshot!.versions" :key="v.version" class="governance-version-row">
                  <div class="governance-version-main">
                    <div class="governance-version-head">
                      <strong>v{{ v.version }}</strong>
                      <span :class="['badge', `status-${v.status}`]">{{ statusText(v.status) }}</span>
                      <span v-if="v.is_yanked" class="badge status-blocked">已 yank</span>
                    </div>
                    <p>{{ v.release_title || v.version }} · {{ formatDate(v.published_at) }} · {{ formatBytes(v.file_size) }} · {{ formatNumber(v.download_count) }} 下载</p>
                    <small>API {{ v.plugin_api_version }} · Host >= {{ v.min_host_version }}{{ v.max_host_version ? ` <= ${v.max_host_version}` : '' }} · {{ (v.supported_platforms || []).join(', ') || 'all' }}</small>
                  </div>
                  <div class="table-actions">
                    <a class="btn btn-xs btn-ghost" :href="v.release_url" target="_blank" rel="noreferrer noopener">Release</a>
                    <button v-if="v.status !== 'published' || v.is_yanked" class="btn btn-xs" @click="versionAction('publish', selectedPlugin.plugin_id, v.version)">恢复</button>
                    <button v-if="v.status !== 'submitted'" class="btn btn-xs" @click="versionAction('reject', selectedPlugin.plugin_id, v.version)">退回</button>
                    <button v-if="!v.is_yanked" class="btn btn-xs" @click="versionAction('yank', selectedPlugin.plugin_id, v.version)">下架</button>
                    <button v-if="v.status !== 'blocked'" class="btn btn-xs btn-danger" @click="versionAction('block', selectedPlugin.plugin_id, v.version)">封禁</button>
                  </div>
                </div>
              </div>
              <EmptyState v-else title="暂无版本" message="当前插件还没有任何版本记录。" />
            </template>
            <EmptyState v-else title="未选择插件" message="先从队列中选择插件。" />
          </div>
        </section>

        <!-- Trends + Review feed -->
        <section class="ops-grid">
          <div class="panel trend-panel" id="admin-trends">
            <div class="section-head compact-head"><div><h2>热门插件观察</h2><p>按趋势热度排序，方便观察社区讨论中心。</p></div></div>
            <div class="trend-list">
              <router-link
                v-for="p in (dashboard?.popular_plugins || [])"
                :key="p.plugin_id"
                class="trend-item"
                :to="`/plugin/${encodeURIComponent(p.plugin_id)}`"
              >
                <div class="trend-item-main"><strong>{{ p.display_name }}</strong><span>{{ p.plugin_id }}</span></div>
                <div class="trend-item-meta"><span>{{ formatNumber(p.comments_count) }} 评</span><span>{{ formatNumber(p.downloads_count) }} 下载</span></div>
              </router-link>
            </div>
          </div>
          <div class="panel review-stream-panel" id="admin-review-feed">
            <div class="section-head compact-head"><div><h2>最近审核流</h2><p>展示最新的插件与版本治理动作。</p></div></div>
            <div v-if="reviews.length" class="review-feed">
              <article v-for="item in [...reviews].reverse().slice(0, 18)" :key="item.id || item.created_at" class="review-feed-item">
                <div>
                  <strong>{{ reviewActionText(item.action) }}</strong>
                  <p>{{ item.target_id }} · {{ item.status_before || '-' }} → {{ item.status_after || '-' }}</p>
                </div>
                <div class="review-feed-meta">
                  <span>{{ item.operator_id }}</span>
                  <span>{{ formatRelative(item.created_at) }}</span>
                </div>
              </article>
            </div>
            <EmptyState v-else title="暂无审核记录" message="" />
          </div>
        </section>

        <!-- Plugin history -->
        <section class="panel review-stream-panel" id="admin-plugin-history">
          <div class="section-head compact-head"><div><h2>当前选中插件的治理历史</h2><p>帮助判断这次要不要恢复上架，还是继续封禁。</p></div></div>
          <template v-if="selectedPlugin">
            <div v-if="(snapshot?.recent_reviews || []).length" class="review-feed">
              <article v-for="item in snapshot!.recent_reviews" :key="item.id || item.created_at" class="review-feed-item">
                <div>
                  <strong>{{ reviewActionText(item.action) }}</strong>
                  <p>{{ item.target_id }} · {{ item.status_before || '-' }} → {{ item.status_after || '-' }}</p>
                </div>
                <div class="review-feed-meta">
                  <span>{{ item.operator_id }}</span>
                  <span>{{ formatRelative(item.created_at) }}</span>
                </div>
              </article>
            </div>
            <EmptyState v-else title="暂无治理历史" message="当前插件暂无治理历史。" />
          </template>
          <EmptyState v-else title="未选择插件" message="先在治理队列中选择插件。" />
        </section>
      </div>
    </div>
  </div>
</template>
