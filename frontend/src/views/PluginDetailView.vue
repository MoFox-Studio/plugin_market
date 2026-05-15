<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { formatNumber, formatRelative, formatDate, formatBytes, categoryLabel, starPercent } from '@/utils/format'
import type { Plugin, RatingInfo, PluginVersion, Dependency, Comment } from '@/types'
import TrustBadge from '@/components/TrustBadge.vue'
import RiskWarning from '@/components/RiskWarning.vue'
import EmptyState from '@/components/EmptyState.vue'

const route = useRoute()
const auth = useAuthStore()
const toast = useToastStore()

const props = defineProps({ id: { type: String, required: true } })

const plugin = ref<Plugin | null>(null)
const rating = ref<RatingInfo | null>(null)
const versions = ref<PluginVersion[]>([])
const readme = ref<{ exists?: boolean; html?: string } | null>(null)
const dependencies = ref<Dependency[]>([])
const comments = ref<Comment[]>([])
const loading = ref(true)
const activeTab = ref('overview')
const commentContent = ref('')
const submittingComment = ref(false)

const pluginId = computed(() => props.id || route.params.id as string)

async function loadData() {
  loading.value = true
  const id = encodeURIComponent(pluginId.value)
  try {
    const [snapshot, versionsRes, readmeRes, depsRes] = await Promise.all([
      api.get(`/api/v1/plugins/${id}/community`),
      api.get(`/api/v1/plugins/${id}/versions`).catch(() => ({ items: [] })),
      api.get(`/api/v1/plugins/${id}/readme`).catch(() => ({ exists: false, html: null })),
      api.get(`/api/v1/plugins/${id}/dependencies`).catch(() => ({ items: [] })),
    ])
    plugin.value = snapshot.plugin
    rating.value = snapshot.rating
    versions.value = versionsRes.items || []
    readme.value = readmeRes
    dependencies.value = depsRes.items || []
    await loadComments()
  } finally {
    loading.value = false
  }
}

async function loadComments() {
  const id = encodeURIComponent(pluginId.value)
  const result = await api.get(`/api/v1/plugins/${id}/comments?limit=50`).catch(() => ({ items: [] }))
  comments.value = result.items || []
}

async function submitComment() {
  const content = commentContent.value.trim()
  if (!content) return
  submittingComment.value = true
  try {
    await api.post(`/api/v1/plugins/${encodeURIComponent(pluginId.value)}/comments`, { content })
    commentContent.value = ''
    toast.show('已发布', 'ok')
    await loadComments()
  } catch (e) {
    toast.show((e as Error).message || '发布失败', 'error')
  } finally {
    submittingComment.value = false
  }
}

async function deleteComment(commentId: string) {
  if (!confirm('确定删除这条评论吗？')) return
  try {
    await api.del(`/api/v1/plugins/${encodeURIComponent(pluginId.value)}/comments/${commentId}`)
    toast.show('已删除', 'ok')
    await loadComments()
  } catch (e) {
    toast.show((e as Error).message || '删除失败', 'error')
  }
}

async function handleInstall() {
  try {
    const v = await api.post(`/api/v1/plugins/${encodeURIComponent(pluginId.value)}/install-record`)
    if (v?.asset_download_url) window.open(v.asset_download_url, '_blank', 'noopener')
    toast.show('已记录下载', 'ok')
  } catch (e) {
    toast.show((e as Error).message || '下载失败', 'error')
  }
}

async function handleLike() {
  if (!auth.isAuthenticated) {
    toast.show('请先登录', '')
    setTimeout(() => { location.href = auth.getLoginUrl() }, 600)
    return
  }
  try {
    const r = await api.post(`/api/v1/plugins/${encodeURIComponent(pluginId.value)}/like`)
    toast.show(r.liked ? '已点赞' : '已取消点赞', 'ok')
    await loadData()
  } catch (e) {
    toast.show((e as Error).message || '操作失败', 'error')
  }
}

async function handleRate(score: number) {
  if (!auth.isAuthenticated) {
    toast.show('请先登录', '')
    setTimeout(() => { location.href = auth.getLoginUrl() }, 600)
    return
  }
  try {
    await api.post(`/api/v1/plugins/${encodeURIComponent(pluginId.value)}/rating`, { score })
    toast.show('感谢你的评分', 'ok')
    await loadData()
  } catch (e) {
    toast.show((e as Error).message || '评分失败', 'error')
  }
}

async function clearRating() {
  try {
    await api.del(`/api/v1/plugins/${encodeURIComponent(pluginId.value)}/rating`)
    toast.show('已清除评分', 'ok')
    await loadData()
  } catch (e) {
    toast.show((e as Error).message || '操作失败', 'error')
  }
}

function recordDownload(version: string) {
  api.post(`/api/v1/plugins/${encodeURIComponent(pluginId.value)}/install-record?version=${encodeURIComponent(version)}`).catch(() => {})
}

function canDeleteComment(comment: Comment) {
  if (!auth.viewer) return false
  return auth.viewer.author_id === comment.author.author_id || auth.viewer.is_admin
}

onMounted(loadData)
</script>

<template>
  <div v-if="loading" class="loading-screen">加载插件详情…</div>
  <template v-else-if="plugin">
    <!-- Breadcrumb -->
    <div style="padding-top:16px;color:var(--muted);font-size:0.82rem">
      <router-link to="/">市场</router-link>
      <span style="margin:0 6px">/</span>
      {{ plugin.display_name }}
    </div>

    <div class="detail">
      <div class="main-col">
        <!-- Hero -->
        <section class="detail-hero">
          <div class="detail-icon">
            <img v-if="plugin.icon_url" :src="plugin.icon_url" alt="">
            <template v-else>{{ (plugin.display_name || '?').trim()[0]?.toUpperCase() || '?' }}</template>
          </div>
          <div>
            <div class="detail-title">
              <h1>{{ plugin.display_name }}</h1>
              <TrustBadge :level="plugin.trust_level" />
              <span :class="['badge', `status-${plugin.status}`]">{{ plugin.status }}</span>
              <span v-if="plugin.latest_version" class="card-version-chip">v{{ plugin.latest_version }}</span>
            </div>
            <div class="detail-sub">
              <span>{{ plugin.plugin_id }}</span>
              <span>·</span>
              <span>作者 <router-link :to="`/author/${encodeURIComponent(plugin.owner_id)}`">{{ plugin.owner_display_name || plugin.owner_login || plugin.owner_id }}</router-link></span>
              <span>·</span>
              <span>{{ plugin.license }}</span>
              <span>·</span>
              <span>更新于 {{ formatRelative(plugin.updated_at) }}</span>
            </div>
          </div>
          <p class="detail-summary">{{ plugin.summary }}</p>
        </section>

        <!-- Tabs -->
        <div class="tabs">
          <button type="button" :class="{ active: activeTab === 'overview' }" @click="activeTab = 'overview'">简介</button>
          <button type="button" :class="{ active: activeTab === 'versions' }" @click="activeTab = 'versions'">版本<span class="count">{{ versions.length }}</span></button>
          <button type="button" :class="{ active: activeTab === 'comments' }" @click="activeTab = 'comments'">评论<span class="count">{{ plugin.comments_count }}</span></button>
        </div>

        <!-- Tab panels -->
        <section v-show="activeTab === 'overview'">
          <div class="panel">
            <h3>插件简介</h3>
            <div class="description">{{ plugin.description || plugin.summary }}</div>
          </div>
          <!-- Dependencies -->
          <div v-if="dependencies.length" class="panel">
            <h3>依赖插件</h3>
            <div class="dependency-list">
              <component
                v-for="dep in dependencies"
                :key="dep.plugin_id"
                :is="dep.exists_in_market ? 'router-link' : 'div'"
                :to="dep.exists_in_market ? `/plugin/${encodeURIComponent(dep.plugin_id)}` : undefined"
                :class="['dependency-chip', { 'is-link': dep.exists_in_market }]"
              >
                <img v-if="dep.icon_url" class="dependency-icon" :src="dep.icon_url" alt="">
                <span v-else class="dependency-icon dependency-icon-fallback">{{ (dep.display_name || dep.plugin_id).trim()[0]?.toUpperCase() || 'P' }}</span>
                <span class="dependency-copy">
                  <strong>{{ dep.display_name || dep.plugin_id }}</strong>
                  <span>{{ dep.plugin_id }}</span>
                </span>
                <span v-if="dep.version_spec" class="dependency-spec">{{ dep.version_spec }}</span>
                <span class="dependency-meta">{{ dep.exists_in_market ? '已收录于市场' : '尚未在市场中找到' }}</span>
              </component>
            </div>
          </div>
          <!-- README -->
          <div v-if="readme?.exists && readme.html" class="panel">
            <h3>README</h3>
            <div class="markdown-content" v-html="readme.html"></div>
          </div>
          <!-- Tags -->
          <div class="panel">
            <h3>分类与标签</h3>
            <div class="card-tags">
              <span v-for="cat in (plugin.categories || [])" :key="cat" class="tag cat">{{ categoryLabel(cat) }}</span>
              <span v-for="t in (plugin.tags || [])" :key="t" class="tag">#{{ t }}</span>
            </div>
          </div>
          <!-- Maintainers -->
          <div class="panel">
            <h3>维护者</h3>
            <div style="color:var(--muted);font-size:0.86rem">
              <template v-for="(m, i) in plugin.maintainers" :key="m">
                <router-link :to="`/author/${encodeURIComponent(m)}`">{{ m }}</router-link>
                <template v-if="i < plugin.maintainers.length - 1"> · </template>
              </template>
            </div>
          </div>
        </section>

        <!-- Versions -->
        <section v-show="activeTab === 'versions'">
          <div class="panel">
            <h3>发布历史</h3>
            <RiskWarning kind="inline" />
            <div v-if="versions.length">
              <div v-for="v in versions" :key="v.version" class="version-item">
                <span class="ver">
                  v{{ v.version }}
                  <small v-if="v.is_prerelease" style="color:var(--warn)">pre</small>
                  <small v-if="v.is_yanked" style="color:var(--bad)">yanked</small>
                </span>
                <div class="meta">
                  <div><strong>{{ v.release_title || v.version }}</strong></div>
                  <div>{{ formatDate(v.published_at) }} · {{ formatBytes(v.file_size) }} · API {{ v.plugin_api_version }} · 宿主 ≥ {{ v.min_host_version }}{{ v.max_host_version ? ` ≤ ${v.max_host_version}` : '' }}</div>
                  <div>{{ formatNumber(v.download_count) }} 次下载 · 平台 {{ (v.supported_platforms || []).join(', ') || 'all' }}</div>
                </div>
                <div class="table-actions">
                  <a class="btn btn-sm" :href="v.release_url" target="_blank" rel="noreferrer noopener">Release</a>
                  <a class="btn btn-sm btn-primary" :href="v.asset_download_url" target="_blank" rel="noreferrer noopener" @click="recordDownload(v.version)">下载</a>
                </div>
              </div>
            </div>
            <EmptyState v-else title="暂无版本" message="作者尚未发布任何已审核通过的版本。" />
          </div>
        </section>

        <!-- Comments -->
        <section v-show="activeTab === 'comments'">
          <div class="panel">
            <h3>评论 <span class="count" style="font-size:0.8rem;color:var(--muted);font-weight:400">{{ plugin.comments_count }} 条</span></h3>
            <!-- Comment form -->
            <div v-if="auth.isAuthenticated">
              <form class="comment-form" @submit.prevent="submitComment">
                <textarea
                  v-model="commentContent"
                  maxlength="4000"
                  placeholder="分享你的安装体验或提出问题..."
                  required
                  :disabled="submittingComment"
                ></textarea>
                <div class="comment-form-actions">
                  <small>支持多行文字。不要发送广告或个人隐私信息。</small>
                  <button class="btn btn-primary btn-sm" type="submit" :disabled="submittingComment">发布评论</button>
                </div>
              </form>
            </div>
            <div v-else class="empty" style="padding:16px">
              登录后可以发表评论与作者互动。
              <div style="margin-top:8px">
                <a class="btn btn-primary btn-sm" :href="auth.getLoginUrl()">
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>
                  GitHub 登录
                </a>
              </div>
            </div>
            <!-- Comment list -->
            <div style="margin-top:14px">
              <div v-if="comments.length">
                <div v-for="c in comments" :key="c.id" class="comment">
                  <div class="comment-avatar">
                    <img v-if="c.author.avatar_url" :src="c.author.avatar_url" alt="">
                    <template v-else>{{ c.author.display_name?.[0]?.toUpperCase() || '?' }}</template>
                  </div>
                  <div>
                    <div class="comment-meta">
                      <strong>{{ c.author.display_name }}</strong>
                      <span>@{{ c.author.github_login }}</span>
                      <span v-if="c.author.is_admin" class="badge trust-official">管理员</span>
                      <span>·</span>
                      <span>{{ formatRelative(c.created_at) }}</span>
                    </div>
                    <p class="comment-content">{{ c.content }}</p>
                    <div class="comment-actions">
                      <button v-if="canDeleteComment(c)" type="button" @click="deleteComment(c.id)">删除</button>
                    </div>
                  </div>
                </div>
              </div>
              <EmptyState v-else title="还没有评论" message="来抢占第一个评论吧！" />
            </div>
          </div>
        </section>
      </div>

      <!-- Sidebar -->
      <aside class="install-panel">
        <div class="panel">
          <h3>安装</h3>
          <RiskWarning kind="panel" />
          <template v-if="plugin.latest_version">
            <div style="color:var(--muted);font-size:0.8rem;margin-bottom:4px">最新稳定版</div>
            <div style="font-family:'JetBrains Mono',Consolas,monospace;font-size:1rem;color:var(--ink);font-weight:600">v{{ plugin.latest_version }}</div>
            <div style="font-size:0.78rem;color:var(--muted)">发布于 {{ formatRelative(plugin.latest_version_published_at) }}</div>
          </template>
          <div v-else style="color:var(--muted)">暂无可安装版本</div>

          <div class="install-stats">
            <div><b>{{ formatNumber(plugin.downloads_count) }}</b><span>下载</span></div>
            <div><b>{{ formatNumber(plugin.likes_count) }}</b><span>点赞</span></div>
            <div><b>{{ plugin.rating_avg.toFixed(1) }}</b><span>{{ plugin.rating_count }} 评价</span></div>
          </div>

          <div class="install-actions">
            <button type="button" class="btn btn-primary" :disabled="!plugin.latest_version" @click="handleInstall">下载插件</button>
            <button type="button" class="btn" @click="handleLike">{{ plugin.viewer_has_liked ? '❤ 已赞' : '♡ 点赞' }}</button>
          </div>

          <code v-if="plugin.latest_version" class="install-code">mofox plugin install {{ plugin.plugin_id }}@{{ plugin.latest_version }}</code>

          <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap;font-size:0.82rem;color:var(--muted)">
            <a v-if="plugin.homepage" :href="plugin.homepage" target="_blank" rel="noreferrer noopener">主页 ↗</a>
            <a :href="plugin.repository_url" target="_blank" rel="noreferrer noopener">GitHub ↗</a>
          </div>
        </div>

        <!-- Rating panel -->
        <div class="panel">
          <h3>评分<span style="font-size:0.8rem;color:var(--muted);font-weight:400">{{ plugin.rating_count }} 票</span></h3>
          <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:6px">
            <div style="font-size:2rem;font-weight:700;color:var(--ink)">{{ plugin.rating_avg.toFixed(1) }}</div>
            <div class="rating">
              <span class="stars" aria-hidden="true">
                ★★★★★
                <span class="fill" :style="{ width: starPercent(plugin.rating_avg) + '%' }">★★★★★</span>
              </span>
            </div>
          </div>
          <!-- Distribution -->
          <div class="rating-dist">
            <div v-for="s in [5, 4, 3, 2, 1]" :key="s" class="rating-dist-row">
              <span>{{ s }}★</span>
              <span class="rating-dist-bar">
                <span :style="{ width: (plugin.rating_count ? Math.round((rating?.distribution?.[String(s)] || 0) / plugin.rating_count * 100) : 0) + '%' }"></span>
              </span>
              <span>{{ rating?.distribution?.[String(s)] || 0 }}</span>
            </div>
          </div>
          <!-- My rating -->
          <div style="margin-top:12px">
            <div style="font-size:0.8rem;color:var(--muted);margin-bottom:4px">我的评分</div>
            <div class="rating-picker">
              <button
                v-for="n in 5"
                :key="n"
                type="button"
                :class="{ active: (rating?.viewer_rating || 0) >= n }"
                @click="handleRate(n)"
              >&#9733;</button>
              <button
                v-if="rating?.viewer_rating"
                type="button"
                class="btn btn-xs btn-ghost"
                style="margin-left:6px"
                @click="clearRating"
              >清除</button>
            </div>
            <div v-if="!auth.isAuthenticated" style="font-size:0.78rem;color:var(--muted);margin-top:4px">登录后可以评分和评论。</div>
          </div>
        </div>
      </aside>
    </div>
  </template>
</template>
