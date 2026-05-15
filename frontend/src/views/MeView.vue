<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { formatNumber, formatRelative, formatDate, formatBytes, statusText, categoryLabel, reviewActionText } from '@/utils/format'
import type { Plugin, PluginSnapshot } from '@/types'
import TrustBadge from '@/components/TrustBadge.vue'
import EmptyState from '@/components/EmptyState.vue'

const auth = useAuthStore()
const toast = useToastStore()

const plugins = ref<Plugin[]>([])
const selectedId = ref<string | null>(null)
const snapshot = ref<PluginSnapshot | null>(null)
const loading = ref(true)

const selectedPlugin = ref<Plugin | null>(null)

async function loadPlugins() {
  const result = await api.get('/api/v1/me/plugins').catch(() => ({ items: [] }))
  plugins.value = result.items || []
  if (!selectedId.value && plugins.value.length) {
    selectedId.value = plugins.value[0].plugin_id
  }
  if (selectedId.value) {
    await loadSnapshot()
  }
}

async function loadSnapshot() {
  if (!selectedId.value) { snapshot.value = null; selectedPlugin.value = null; return }
  const s = await api.get(`/api/v1/me/plugins/${encodeURIComponent(selectedId.value)}`).catch(() => null)
  snapshot.value = s
  selectedPlugin.value = s?.plugin || null
}

async function selectPlugin(id: string) {
  selectedId.value = id
  await loadSnapshot()
}

async function yankVersion(pluginId: string, version: string) {
  if (!confirm(`确认下架 ${pluginId}@${version} 吗？`)) return
  const reason = prompt('可填写下架原因，留空也可以。', '') || ''
  try {
    await api.post(`/api/v1/me/plugins/${encodeURIComponent(pluginId)}/versions/${encodeURIComponent(version)}/yank`, reason.trim() ? { reason: reason.trim() } : {})
    toast.show('版本已下架', 'ok')
    await loadSnapshot()
  } catch (e) {
    toast.show((e as Error).message || '操作失败', 'error')
  }
}

async function deletePlugin(pluginId: string) {
  if (!confirm(`确认彻底删除 ${pluginId} 吗？这个操作不可撤销。`)) return
  try {
    await api.del(`/api/v1/me/plugins/${encodeURIComponent(pluginId)}`)
    selectedId.value = null
    snapshot.value = null
    selectedPlugin.value = null
    toast.show('插件已删除', 'ok')
    await loadPlugins()
  } catch (e) {
    toast.show((e as Error).message || '删除失败', 'error')
  }
}

onMounted(async () => {
  loading.value = true
  await loadPlugins()
  loading.value = false
})
</script>

<template>
  <!-- Not logged in -->
  <div v-if="!auth.isAuthenticated" style="padding-top:40px">
    <EmptyState title="请先登录" message="使用 GitHub 账号登录后，才能管理自己的插件与版本。" />
    <div style="text-align:center;margin-top:12px">
      <a class="btn btn-primary" :href="auth.getLoginUrl('/me')">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>
        GitHub 登录
      </a>
    </div>
  </div>

   <!-- Logged in -->
  <div v-else class="control-room">
    <!-- Hero -->
    <section v-if="auth.viewer" class="control-hero creator-hero">
      <div class="control-hero-copy">
        <span class="control-kicker">Creator Studio</span>
        <h1>我的插件工作台</h1>
        <p>在这里处理版本下架、检查最近审核反馈、决定是否彻底删除插件。</p>
        <div class="control-pills">
          <span class="control-pill">@{{ auth.viewer.github_login }}</span>
          <span class="control-pill">{{ plugins.length }} 个管理中的插件</span>
          <span class="control-pill">{{ plugins.filter(p => p.status === 'published').length }} 个正在上架</span>
        </div>
      </div>
      <div class="profile-card">
        <img v-if="auth.viewer.avatar_url" :src="auth.viewer.avatar_url" alt="">
        <div v-else class="profile-card-fallback">M</div>
        <div>
          <strong>{{ auth.viewer.display_name }}</strong>
          <span>{{ auth.viewer.author_id }}</span>
          <div class="table-actions">
            <router-link class="btn btn-sm" :to="`/author/${encodeURIComponent(auth.viewer.author_id)}`">公开主页</router-link>
            <a class="btn btn-sm btn-ghost" :href="`https://github.com/${encodeURIComponent(auth.viewer.github_login)}`" target="_blank" rel="noreferrer noopener">GitHub</a>
          </div>
        </div>
      </div>
    </section>

    <!-- Layout -->
    <div class="control-layout">
      <aside class="panel control-sidebar">
        <div class="section-head compact-head">
          <div><h2>插件列表</h2><p>选择一个插件查看版本与治理记录。</p></div>
        </div>
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
        <EmptyState v-else title="还没有插件" message="使用 MPDT CLI 上传第一个插件后，这里会出现管理入口。" />
      </aside>

      <div class="control-main">
        <template v-if="selectedPlugin">
          <!-- Metrics -->
          <section class="control-metrics-row">
            <div class="control-metric"><span>当前状态</span><b>{{ statusText(selectedPlugin.status) }}</b><small>最近更新 {{ formatRelative(selectedPlugin.updated_at) }}</small></div>
            <div class="control-metric"><span>版本总数</span><b>{{ snapshot?.versions?.length || 0 }}</b><small>{{ (snapshot?.versions || []).filter(v => v.is_yanked).length }} 个已下架</small></div>
            <div class="control-metric"><span>社区反馈</span><b>{{ formatNumber(selectedPlugin.comments_count) }} / {{ formatNumber(selectedPlugin.rating_count) }}</b><small>评论 / 评分</small></div>
            <div class="control-metric"><span>热度</span><b>{{ formatNumber(selectedPlugin.likes_count) }} ❤</b><small>{{ formatNumber(selectedPlugin.downloads_count) }} 下载</small></div>
          </section>

          <section class="ops-grid single-column-layout">
            <!-- Plugin info -->
            <div class="panel plugin-sheet">
              <div class="section-head compact-head">
                <div><h2>{{ selectedPlugin.display_name }}</h2><p>{{ selectedPlugin.summary }}</p></div>
                <div class="table-actions">
                  <span :class="['badge', `status-${selectedPlugin.status}`]">{{ statusText(selectedPlugin.status) }}</span>
                  <TrustBadge :level="selectedPlugin.trust_level" />
                </div>
              </div>
              <div class="plugin-sheet-grid">
                <div>
                  <h4>基础信息</h4>
                  <ul class="meta-list">
                    <li><span>插件 ID</span><strong>{{ selectedPlugin.plugin_id }}</strong></li>
                    <li><span>最新版本</span><strong>{{ selectedPlugin.latest_version || '-' }}</strong></li>
                    <li><span>分类标签</span><strong>{{ [...(selectedPlugin.categories || []).map(categoryLabel), ...(selectedPlugin.tags || [])].join(' / ') || '未设置' }}</strong></li>
                    <li><span>仓库</span><strong><a :href="selectedPlugin.repository_url" target="_blank" rel="noreferrer noopener">查看源码</a></strong></li>
                  </ul>
                </div>
                <div>
                  <h4>危险操作</h4>
                  <p class="soft-note">删除会移除插件、版本、评论与审核记录。建议只在确认废弃整个项目时使用。</p>
                  <div class="table-actions">
                    <button class="btn btn-danger" @click="deletePlugin(selectedPlugin.plugin_id)">删除插件</button>
                  </div>
                </div>
              </div>
            </div>

            <!-- Version governance -->
            <div class="panel version-governance">
              <div class="section-head compact-head">
                <div><h2>版本管理</h2><p>支持一键下架存在问题的版本，前台会立即停止推荐该版本。</p></div>
              </div>
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
                    <button v-if="!v.is_yanked" class="btn btn-xs" @click="yankVersion(selectedPlugin.plugin_id, v.version)">下架此版本</button>
                  </div>
                </div>
              </div>
              <EmptyState v-else title="暂无版本" message="当前插件还没有任何可管理的版本。" />
            </div>

            <!-- Review history -->
            <div class="panel review-stream-panel">
              <div class="section-head compact-head">
                <div><h2>最近治理记录</h2><p>这里会显示后台对该插件与版本的最近操作。</p></div>
              </div>
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
              <EmptyState v-else title="暂无记录" message="这个插件还没有任何治理记录。" />
            </div>
          </section>
        </template>
        <section v-else class="panel">
          <EmptyState title="还没有可管理的插件" message="上传插件后，这里会展示版本和治理控制入口。" />
        </section>
      </div>
    </div>
  </div>
</template>
