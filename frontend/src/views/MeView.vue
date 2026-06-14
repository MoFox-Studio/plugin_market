<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { useTaxonomyStore } from '@/stores/taxonomy'
import { formatNumber, formatRelative, formatDate, formatBytes, statusText, categoryLabel, reviewActionText, EDITABLE_PLUGIN_CATEGORIES } from '@/utils/format'
import type { AccessTokenStatus, MyFollowItem, MyFollowListResponse, MySubscriptionItem, MySubscriptionListResponse, Plugin, PluginMetadataPatch, PluginSnapshot, Skill } from '@/types'
import TrustBadge from '@/components/TrustBadge.vue'
import EmptyState from '@/components/EmptyState.vue'

import { useSubscriptionStore } from '@/stores/subscriptions'

const auth = useAuthStore()
const toast = useToastStore()
const taxonomy = useTaxonomyStore()
const subStore = useSubscriptionStore()

const plugins = ref<Plugin[]>([])
const selectedId = ref<string | null>(null)
const snapshot = ref<PluginSnapshot | null>(null)
const loading = ref(true)
const selectedPlugin = ref<Plugin | null>(null)
const metadataOpen = ref(false)
const metadataSaving = ref(false)
const metadataDisplayName = ref('')
const metadataIconUrl = ref('')
const metadataCategory = ref('')
const metadataTags = ref('')
const iconFileInput = ref<HTMLInputElement | null>(null)
const iconUploading = ref(false)
const accessToken = ref<AccessTokenStatus | null>(null)
const accessTokenValue = ref('')
const accessTokenBusy = ref(false)

const subscriptions = ref<MySubscriptionItem[]>([])
const subscriptionsBusy = ref(false)
const follows = ref<MyFollowItem[]>([])
const followsBusy = ref(false)

// --- skills ---
const mySkills = ref<Skill[]>([])
const skillsBusy = ref(false)
const skillPublishOpen = ref(false)
const skillPublishSaving = ref(false)
const skillPublishSkillId = ref('')
const skillPublishVersion = ref('0.1.0')
const skillPublishNotes = ref('')
const skillPublishCategories = ref('')
const skillPublishTags = ref('')
const skillZipInput = ref<HTMLInputElement | null>(null)
const skillZipFile = ref<File | null>(null)

async function copyText(value: string, successMessage: string) {
  try {
    await navigator.clipboard.writeText(value)
    toast.show(successMessage, 'ok')
  } catch {
    toast.show('复制失败，请检查浏览器权限', 'error')
  }
}

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

async function loadAccessToken() {
  accessToken.value = await api.me.accessToken.get().catch(() => null)
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

function openMetadataEditor() {
  if (!selectedPlugin.value) return
  metadataDisplayName.value = selectedPlugin.value.display_name || ''
  metadataIconUrl.value = selectedPlugin.value.icon_url || ''
  metadataCategory.value = selectedPlugin.value.categories?.[0] || ''
  metadataTags.value = (selectedPlugin.value.tags || []).join(', ')
  metadataOpen.value = true
}

function closeMetadataEditor() { metadataOpen.value = false }

function pickIcon() {
  iconFileInput.value?.click()
}

async function onIconFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !selectedPlugin.value) return
  if (file.size > 2 * 1024 * 1024) {
    toast.show('图标不能超过 2 MiB', 'error')
    return
  }
  iconUploading.value = true
  try {
    const updated = await api.me.plugins.uploadIcon(selectedPlugin.value.plugin_id, file)
    selectedPlugin.value = updated
    metadataIconUrl.value = updated.icon_url || ''
    plugins.value = plugins.value.map((plugin) => plugin.plugin_id === updated.plugin_id ? updated : plugin)
    if (snapshot.value) snapshot.value = { ...snapshot.value, plugin: updated }
    toast.show('图标已上传', 'ok')
  } catch (e) {
    toast.show((e as Error).message || '上传失败', 'error')
  } finally {
    iconUploading.value = false
  }
}

async function saveMetadataPatch() {
  if (!selectedPlugin.value) return
  const payload: PluginMetadataPatch = {
    display_name: metadataDisplayName.value.trim() || selectedPlugin.value.display_name,
    icon_url: metadataIconUrl.value.trim() || null,
    categories: metadataCategory.value ? [metadataCategory.value] : [],
    tags: metadataTags.value.split(',').map((item) => item.trim()).filter(Boolean),
  }
  metadataSaving.value = true
  try {
    const updated = await api.me.plugins.patchMetadata(selectedPlugin.value.plugin_id, payload)
    selectedPlugin.value = updated
    plugins.value = plugins.value.map((plugin) => plugin.plugin_id === updated.plugin_id ? updated : plugin)
    if (snapshot.value) snapshot.value = { ...snapshot.value, plugin: updated }
    metadataOpen.value = false
    toast.show('插件资料已更新', 'ok')
  } catch (e) {
    toast.show((e as Error).message || '更新失败', 'error')
  } finally {
    metadataSaving.value = false
  }
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

async function rotateAccessToken() {
  accessTokenBusy.value = true
  try {
    const rotated = await api.me.accessToken.rotate()
    accessTokenValue.value = rotated.token
    await loadAccessToken()
    toast.show('已生成新访问令牌，旧令牌已失效', 'ok')
  } catch (e) {
    toast.show((e as Error).message || '生成失败', 'error')
  } finally {
    accessTokenBusy.value = false
  }
}

async function revokeAccessToken() {
  if (!confirm('确认撤销当前访问令牌吗？Neo-MoFox 将无法继续从市场同步订阅。')) return
  accessTokenBusy.value = true
  try {
    accessToken.value = await api.me.accessToken.revoke()
    accessTokenValue.value = ''
    toast.show('访问令牌已撤销', 'ok')
  } catch (e) {
    toast.show((e as Error).message || '撤销失败', 'error')
  } finally {
    accessTokenBusy.value = false
  }
}

async function loadSubscriptions() {
  const result = await api.me.subscriptions().catch(() => ({ author_id: '', items: [], total: 0 } as MySubscriptionListResponse))
  subscriptions.value = result.items || []
}

async function loadFollows() {
  const result = await api.me.follows().catch(() => ({ author_id: '', items: [], total: 0 } as MyFollowListResponse))
  follows.value = result.items || []
}

async function unsubscribe(pluginId: string) {
  subscriptionsBusy.value = true
  try {
    const result = await api.plugins.toggleSubscription(pluginId)
    subStore.set(pluginId, result.subscribed)
    subscriptions.value = subscriptions.value.filter(item => item.plugin_id !== pluginId)
    toast.show('已取消订阅', 'ok')
  } catch (e) {
    toast.show((e as Error).message || '操作失败', 'error')
  } finally {
    subscriptionsBusy.value = false
  }
}

async function unfollow(authorId: string) {
  followsBusy.value = true
  try {
    await api.authors.toggleFollow(authorId)
    follows.value = follows.value.filter(item => item.author_id !== authorId)
    toast.show('已取消关注', 'ok')
  } catch (e) {
    toast.show((e as Error).message || '操作失败', 'error')
  } finally {
    followsBusy.value = false
  }
}

// --- skills ---
async function loadMySkills() {
  skillsBusy.value = true
  try {
    mySkills.value = await api.skills.my()
  } catch {
    mySkills.value = []
  } finally {
    skillsBusy.value = false
  }
}

function openSkillPublish() {
  skillPublishSkillId.value = ''
  skillPublishVersion.value = '0.1.0'
  skillPublishNotes.value = ''
  skillPublishCategories.value = ''
  skillPublishTags.value = ''
  skillZipFile.value = null
  skillPublishOpen.value = true
}

function closeSkillPublish() { skillPublishOpen.value = false }

function pickSkillZip() { skillZipInput.value?.click() }

function onSkillZipChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (file) skillZipFile.value = file
}

async function publishSkill() {
  if (!skillZipFile.value) { toast.show('请选择 zip 文件', 'error'); return }
  if (!skillPublishSkillId.value.trim()) { toast.show('请输入 Skill ID', 'error'); return }
  skillPublishSaving.value = true
  try {
    const fd = new FormData()
    fd.append('file', skillZipFile.value)
    fd.append('skill_id', skillPublishSkillId.value.trim())
    fd.append('version', skillPublishVersion.value.trim() || '0.1.0')
    if (skillPublishNotes.value.trim()) fd.append('release_notes', skillPublishNotes.value.trim())
    if (skillPublishCategories.value.trim()) {
      const cats = skillPublishCategories.value.split(',').map(s => s.trim()).filter(Boolean)
      cats.forEach(c => fd.append('categories', c))
    }
    if (skillPublishTags.value.trim()) {
      const tgs = skillPublishTags.value.split(',').map(s => s.trim()).filter(Boolean)
      tgs.forEach(t => fd.append('tags', t))
    }
    await api.skills.create(fd)
    skillPublishOpen.value = false
    toast.show('Skill 发布成功！', 'ok')
    await loadMySkills()
  } catch (e) {
    toast.show((e as Error).message || '发布失败', 'error')
  } finally {
    skillPublishSaving.value = false
  }
}

async function deleteSkill(skillId: string) {
  if (!confirm(`确认删除 ${skillId} 吗？`)) return
  try {
    await api.skills.delete(skillId)
    mySkills.value = mySkills.value.filter(s => s.skill_id !== skillId)
    toast.show('Skill 已删除', 'ok')
  } catch (e) {
    toast.show((e as Error).message || '删除失败', 'error')
  }
}

onMounted(async () => {
  loading.value = true
  await Promise.all([loadPlugins(), loadAccessToken(), loadSubscriptions(), loadFollows(), loadMySkills(), taxonomy.load()])
  loading.value = false
})
</script>

<template>
  <div class="me-page" v-if="!auth.isAuthenticated">
    <div class="me-empty">
      <EmptyState title="请先登录" message="使用 GitHub 账号登录后，才能管理自己的插件与版本。" />
      <div class="me-empty-cta">
        <a class="btn btn-primary" :href="auth.getLoginUrl('/me')">GitHub 登录</a>
      </div>
    </div>
  </div>

  <div class="me-page" v-else>
    <!-- Hero -->
    <header class="me-hero" v-if="auth.viewer" data-anim="enter-1">
      <div class="me-hero-bg" aria-hidden="true"></div>
      <div class="me-hero-inner">
        <div class="me-hero-left">
          <span class="kicker">CREATOR STUDIO</span>
          <h1>我的插件工作台</h1>
          <p>治理与版本操作留在这里，个人空间资料请到独立页面维护。</p>
          <div class="me-hero-pills">
            <span class="pill">@{{ auth.viewer.github_login }}</span>
            <span class="pill">{{ plugins.length }} 个插件</span>
            <span class="pill">{{ plugins.filter(p => p.status === 'published').length }} 个上架中</span>
          </div>
        </div>
        <div class="me-hero-right">
          <div class="me-hero-avatar">
            <img v-if="auth.viewer.avatar_url" :src="auth.viewer.avatar_url" alt="">
            <span v-else>{{ auth.viewer.display_name[0]?.toUpperCase() || 'M' }}</span>
          </div>
          <div class="me-hero-meta">
            <strong>{{ auth.viewer.display_name }}</strong>
            <small>{{ auth.viewer.author_id }}</small>
            <div class="me-hero-actions">
              <button type="button" class="btn btn-sm" @click="copyText(auth.viewer.author_id, '用户 ID 已复制')">复制用户 ID</button>
              <router-link class="btn btn-sm" :to="{ name: 'me-profile' }">个人空间设置</router-link>
              <router-link class="btn btn-sm btn-ghost" :to="`/author/${encodeURIComponent(auth.viewer.author_id)}`">查看公开主页</router-link>
            </div>
          </div>
        </div>
      </div>
    </header>

    <section class="me-token-card" v-if="auth.viewer" data-anim="enter-2">
      <div>
        <span class="kicker">MARKET TOKEN</span>
        <h2>插件市场访问令牌</h2>
        <p>Neo-MoFox 接入插件市场时使用这个单实例令牌。重新生成后，旧令牌会立即失效。</p>
      </div>
      <div class="me-token-meta">
        <div class="me-token-summary">
          <span class="badge" :class="accessToken?.has_token ? 'status-published' : 'status-archived'">
            {{ accessToken?.has_token ? '已启用' : '未生成' }}
          </span>
          <span v-if="accessToken?.token_preview" class="me-token-preview">{{ accessToken.token_preview }}</span>
          <span v-if="accessToken?.last_used_at" class="me-token-used">最近使用 {{ formatRelative(accessToken.last_used_at) }}</span>
        </div>
        <div class="me-token-actions">
          <button type="button" class="btn btn-sm" :disabled="accessTokenBusy" @click="rotateAccessToken">
            {{ accessToken?.has_token ? '重新生成令牌' : '生成令牌' }}
          </button>
          <button type="button" class="btn btn-sm btn-ghost" :disabled="!accessToken?.has_token || accessTokenBusy" @click="revokeAccessToken">撤销</button>
        </div>
      </div>
      <div v-if="accessTokenValue" class="me-token-secret">
        <span>新令牌</span>
        <code>{{ accessTokenValue }}</code>
        <button type="button" class="btn btn-sm" @click="copyText(accessTokenValue, '访问令牌已复制')">复制令牌</button>
      </div>
    </section>

    <div class="me-sub-follow-grid" data-anim="enter-3">
      <section class="me-sub-card">
        <div class="me-section-head">
          <h2>我的订阅</h2>
          <small>{{ subscriptions.length }}</small>
        </div>
        <div v-if="subscriptions.length" class="me-sub-list">
          <div v-for="item in subscriptions" :key="item.plugin_id" class="me-sub-row">
            <div class="me-sub-row-icon">
              <img v-if="item.icon_url" :src="item.icon_url" :alt="item.display_name">
              <template v-else>{{ item.display_name[0]?.toUpperCase() || '?' }}</template>
            </div>
            <div class="me-sub-row-info">
              <div class="me-sub-row-head">
                <router-link :to="`/plugin/${encodeURIComponent(item.plugin_id)}`" class="me-sub-row-name">{{ item.display_name }}</router-link>
                <span :class="['badge', `status-${item.status}`]">{{ statusText(item.status) }}</span>
              </div>
              <small class="me-sub-row-meta">{{ item.plugin_id }} · {{ item.owner_display_name || item.owner_login || item.owner_id }} · 订阅于 {{ formatRelative(item.subscribed_at) }}</small>
            </div>
            <button type="button" class="btn btn-sm btn-ghost" :disabled="subscriptionsBusy" @click="unsubscribe(item.plugin_id)">取消订阅</button>
          </div>
        </div>
        <EmptyState v-else title="暂无订阅" message="浏览插件市场，订阅感兴趣的项目后，这里会集中展示。" />
      </section>

      <section class="me-sub-card">
        <div class="me-section-head">
          <h2>我的关注</h2>
          <small>{{ follows.length }}</small>
        </div>
        <div v-if="follows.length" class="me-sub-list">
          <div v-for="item in follows" :key="item.author_id" class="me-sub-row">
            <div class="me-sub-row-icon">
              <img v-if="item.avatar_url" :src="item.avatar_url" :alt="item.display_name">
              <template v-else>{{ item.display_name[0]?.toUpperCase() || '?' }}</template>
            </div>
            <div class="me-sub-row-info">
              <div class="me-sub-row-head">
                <router-link :to="`/author/${encodeURIComponent(item.author_id)}`" class="me-sub-row-name">{{ item.display_name }}</router-link>
              </div>
              <small class="me-sub-row-meta">@{{ item.github_login }} · {{ item.author_id }} · 关注于 {{ formatRelative(item.followed_at) }}</small>
            </div>
            <button type="button" class="btn btn-sm btn-ghost" :disabled="followsBusy" @click="unfollow(item.author_id)">取消关注</button>
          </div>
        </div>
        <EmptyState v-else title="暂无关注" message="关注作者后，这里会集中展示你关注的创作者。" />
      </section>
    </div>

    <!-- My Skills -->
    <section class="me-card" data-anim="enter-3">
      <div class="me-section-head">
        <h2>我的 Skills</h2>
        <small>{{ mySkills.length }}</small>
      </div>
      <div v-if="mySkills.length" class="me-sub-list">
        <div v-for="sk in mySkills" :key="sk.skill_id" class="me-sub-row">
          <div class="me-sub-row-icon">
            <img v-if="sk.icon_url" :src="sk.icon_url" :alt="sk.display_name">
            <template v-else>{{ sk.display_name[0]?.toUpperCase() || '?' }}</template>
          </div>
          <div class="me-sub-row-info">
            <div class="me-sub-row-head">
              <router-link :to="`/skill/${encodeURIComponent(sk.skill_id)}`" class="me-sub-row-name">{{ sk.display_name }}</router-link>
              <span v-if="sk.latest_version" class="badge status-published">v{{ sk.latest_version }}</span>
            </div>
            <small class="me-sub-row-meta">{{ sk.skill_id }} · ⬇ {{ sk.download_count }} · ⭐ {{ sk.rating_avg?.toFixed(1) || '-' }} · {{ formatRelative(sk.updated_at) }}</small>
          </div>
          <button type="button" class="btn btn-sm btn-ghost" @click="deleteSkill(sk.skill_id)">删除</button>
        </div>
      </div>
      <EmptyState v-else title="还没有 Skill" message="发布你的第一个 Skill 吧！" />
      <div style="margin-top: var(--space-3)">
        <button type="button" class="btn btn-primary btn-sm" @click="openSkillPublish">发布新 Skill</button>
      </div>
    </section>

    <div class="me-layout" data-anim="enter-4">
      <!-- Plugin list (left) -->
      <aside class="me-plugin-list">
        <div class="me-section-head">
          <h2>我的插件</h2>
          <small>{{ plugins.length }}</small>
        </div>
        <div v-if="plugins.length" class="me-plugin-rail">
          <button
            v-for="p in plugins"
            :key="p.plugin_id"
            type="button"
            :class="['me-plugin-item', { 'is-active': p.plugin_id === selectedId }]"
            @click="selectPlugin(p.plugin_id)"
          >
            <div class="me-plugin-item-icon">
              <img v-if="p.icon_url" :src="p.icon_url" :alt="p.display_name">
              <template v-else>{{ p.display_name[0]?.toUpperCase() || '?' }}</template>
            </div>
            <div class="me-plugin-item-info">
              <strong>{{ p.display_name }}</strong>
              <small>{{ p.plugin_id }}</small>
              <div class="me-plugin-item-meta">
                <span :class="['badge', `status-${p.status}`]">{{ statusText(p.status) }}</span>
                <span class="muted">{{ formatRelative(p.updated_at) }}</span>
              </div>
            </div>
          </button>
        </div>
        <EmptyState v-else title="还没有插件" message="使用 MPDT CLI 上传第一个插件后，这里会出现管理入口。" />
      </aside>

      <!-- Main detail -->
      <main class="me-main">

        <template v-if="selectedPlugin">
          <section class="me-metric-row">
            <div class="me-metric">
              <span>当前状态</span>
              <strong>{{ statusText(selectedPlugin.status) }}</strong>
              <small>{{ formatRelative(selectedPlugin.updated_at) }}</small>
            </div>
            <div class="me-metric">
              <span>版本总数</span>
              <strong>{{ snapshot?.versions?.length || 0 }}</strong>
              <small>{{ (snapshot?.versions || []).filter(v => v.is_yanked).length }} 个已下架</small>
            </div>
            <div class="me-metric">
              <span>社区</span>
              <strong>{{ formatNumber(selectedPlugin.comments_count) }} / {{ formatNumber(selectedPlugin.rating_count) }}</strong>
              <small>评论 / 评分</small>
            </div>
            <div class="me-metric">
              <span>热度</span>
              <strong>{{ formatNumber(selectedPlugin.likes_count) }} 订阅</strong>
              <small>{{ formatNumber(selectedPlugin.downloads_count) }} 下载</small>
            </div>
          </section>

          <section class="me-card">
            <div class="me-section-head">
              <div>
                <h2>{{ selectedPlugin.display_name }}</h2>
                <p class="me-section-summary">{{ selectedPlugin.summary }}</p>
              </div>
              <div class="me-section-actions">
                <button class="btn btn-sm" @click="openMetadataEditor">编辑资料</button>
                <span :class="['badge', `status-${selectedPlugin.status}`]">{{ statusText(selectedPlugin.status) }}</span>
                <TrustBadge :level="selectedPlugin.trust_level" />
              </div>
            </div>
            <div class="me-info-grid">
              <div>
                <h4>基础信息</h4>
                <ul class="me-meta-list">
                  <li><span>插件 ID</span><strong>{{ selectedPlugin.plugin_id }}</strong></li>
                  <li><span>最新版本</span><strong>{{ selectedPlugin.latest_version || '-' }}</strong></li>
                  <li>
                    <span>分类标签</span>
                    <strong>{{ [...(selectedPlugin.categories || []).map(categoryLabel), ...(selectedPlugin.tags || [])].join(' / ') || '未设置' }}</strong>
                  </li>
                  <li>
                    <span>仓库</span>
                    <strong><a :href="selectedPlugin.repository_url" target="_blank" rel="noreferrer noopener">查看源码 →</a></strong>
                  </li>
                </ul>
              </div>
              <div>
                <h4>危险操作</h4>
                <p class="me-soft-note">删除会移除插件、版本、评论与审核记录。建议只在确认废弃整个项目时使用。</p>
                <button class="btn btn-danger" @click="deletePlugin(selectedPlugin.plugin_id)">删除插件</button>
              </div>
            </div>
          </section>

          <section class="me-card">
            <div class="me-section-head">
              <h2>版本管理</h2>
              <small v-if="snapshot?.versions?.length">{{ snapshot.versions.length }} 个版本</small>
            </div>
            <div v-if="(snapshot?.versions || []).length" class="me-version-list">
              <div v-for="v in snapshot!.versions" :key="v.version" class="me-version-row">
                <div class="me-version-main">
                  <div class="me-version-head">
                    <strong>v{{ v.version }}</strong>
                    <span :class="['badge', `status-${v.status}`]">{{ statusText(v.status) }}</span>
                    <span v-if="v.is_yanked" class="badge status-blocked">已 yank</span>
                  </div>
                  <p>{{ v.release_title || v.version }}</p>
                  <small>{{ formatDate(v.published_at) }} · {{ formatBytes(v.file_size) }} · {{ formatNumber(v.download_count) }} 下载 · API {{ v.plugin_api_version }} · Host >= {{ v.min_host_version }}{{ v.max_host_version ? ` <= ${v.max_host_version}` : '' }}</small>
                </div>
                <div class="me-version-actions">
                  <a class="btn btn-xs btn-ghost" :href="v.release_url" target="_blank" rel="noreferrer noopener">Release</a>
                  <button v-if="!v.is_yanked" class="btn btn-xs" @click="yankVersion(selectedPlugin.plugin_id, v.version)">下架</button>
                </div>
              </div>
            </div>
            <EmptyState v-else title="暂无版本" message="当前插件还没有任何可管理的版本。" />
          </section>

          <section class="me-card">
            <div class="me-section-head">
              <h2>最近治理记录</h2>
            </div>
            <div v-if="(snapshot?.recent_reviews || []).length" class="me-review-feed">
              <article v-for="item in snapshot!.recent_reviews" :key="item.id || item.created_at" class="me-review-item">
                <div>
                  <strong>{{ reviewActionText(item.action) }}</strong>
                  <p>{{ item.target_id }} · {{ item.status_before || '-' }} → {{ item.status_after || '-' }}</p>
                </div>
                <div class="me-review-meta">
                  <span>{{ item.operator_id }}</span>
                  <span>{{ formatRelative(item.created_at) }}</span>
                </div>
              </article>
            </div>
            <EmptyState v-else title="暂无记录" message="这个插件还没有任何治理记录。" />
          </section>
        </template>
        <section v-else class="me-card">
          <EmptyState title="还没有可管理的插件" message="选中左侧任意插件后，这里会展示版本和治理控制入口。" />
        </section>
      </main>
    </div>

    <!-- Metadata editor modal -->
    <div v-if="metadataOpen" class="me-modal-backdrop" @click.self="closeMetadataEditor">
      <section class="me-modal">
        <header class="me-modal-head">
          <div>
            <span class="kicker">EDIT METADATA</span>
            <h2>编辑插件资料</h2>
          </div>
          <button type="button" class="btn btn-ghost btn-sm" @click="closeMetadataEditor">关闭</button>
        </header>
        <div class="me-modal-body">
          <label class="me-form-field">
            <span>显示名</span>
            <input v-model="metadataDisplayName" type="text" maxlength="80">
          </label>
          <label class="me-form-field">
            <span>图标</span>
            <div class="me-form-icon-row">
              <input v-model="metadataIconUrl" type="url" placeholder="https://... 或上传后自动填入">
              <button type="button" class="btn btn-sm" :disabled="iconUploading" @click="pickIcon">{{ iconUploading ? '上传中…' : '上传图标' }}</button>
              <input ref="iconFileInput" class="me-form-file" type="file" accept="image/png,image/jpeg,image/webp,image/gif" @change="onIconFileChange">
            </div>
            <small class="me-form-hint">支持 PNG / JPEG / WEBP / GIF，最大 2 MiB，会归一化为 512×512 PNG。</small>
          </label>
          <label class="me-form-field">
            <span>分类</span>
            <select v-model="metadataCategory">
              <option value="">未设置</option>
              <option v-for="item in EDITABLE_PLUGIN_CATEGORIES" :key="item" :value="item">{{ categoryLabel(item) }}</option>
            </select>
            <small class="me-form-hint">当前仅支持选择一个分类：聊天互动、休闲娱乐、信息资讯、社区管理、实用工具。</small>
          </label>
          <label class="me-form-field">
            <span>标签（用逗号分隔）</span>
            <input v-model="metadataTags" type="text" placeholder="例如 chat, group, fun">
          </label>
        </div>
        <footer class="me-modal-foot">
          <button type="button" class="btn btn-ghost" :disabled="metadataSaving" @click="closeMetadataEditor">取消</button>
          <button type="button" class="btn btn-primary" :disabled="metadataSaving" @click="saveMetadataPatch">{{ metadataSaving ? '保存中…' : '保存' }}</button>
        </footer>
      </section>
    </div>

    <!-- Skill publish modal -->
    <div v-if="skillPublishOpen" class="me-modal-backdrop" @click.self="closeSkillPublish">
      <section class="me-modal">
        <header class="me-modal-head">
          <div>
            <span class="kicker">PUBLISH SKILL</span>
            <h2>发布新 Skill</h2>
          </div>
          <button type="button" class="btn btn-ghost btn-sm" @click="closeSkillPublish">关闭</button>
        </header>
        <div class="me-modal-body">
          <label class="me-form-field">
            <span>Skill ID</span>
            <input v-model="skillPublishSkillId" type="text" placeholder="例如 arxiv-watcher" maxlength="120">
          </label>
          <label class="me-form-field">
            <span>版本号</span>
            <input v-model="skillPublishVersion" type="text" placeholder="0.1.0">
          </label>
          <label class="me-form-field">
            <span>更新说明（可选）</span>
            <input v-model="skillPublishNotes" type="text" placeholder="初始版本">
          </label>
          <label class="me-form-field">
            <span>分类（用逗号分隔）</span>
            <input v-model="skillPublishCategories" type="text" placeholder="工具, 开发">
          </label>
          <label class="me-form-field">
            <span>标签（用逗号分隔）</span>
            <input v-model="skillPublishTags" type="text" placeholder="ai, paper">
          </label>
          <label class="me-form-field">
            <span>Skill Zip 包</span>
            <div class="me-form-icon-row">
              <input type="text" readonly :value="skillZipFile?.name || '未选择文件'" placeholder="选择 zip 文件…">
              <button type="button" class="btn btn-sm" @click="pickSkillZip">选择文件</button>
              <input ref="skillZipInput" class="me-form-file" type="file" accept=".zip" @change="onSkillZipChange">
            </div>
            <small class="me-form-hint">上传包含 SKILL.md 的 zip 包，最大 10 MiB。</small>
          </label>
        </div>
        <footer class="me-modal-foot">
          <button type="button" class="btn btn-ghost" :disabled="skillPublishSaving" @click="closeSkillPublish">取消</button>
          <button type="button" class="btn btn-primary" :disabled="skillPublishSaving || !skillZipFile" @click="publishSkill">{{ skillPublishSaving ? '发布中…' : '发布' }}</button>
        </footer>
      </section>
    </div>
  </div>
</template>

<style scoped>
.me-page {
  width: min(var(--shell-max), 100%);
  margin: 0 auto;
  padding: var(--space-6) var(--space-7) var(--space-16);
  display: grid;
  gap: var(--space-7);
}
@media (max-width: 768px) {
  .me-page { padding: var(--space-4) var(--space-4) var(--space-12); }
}

.me-empty { display: grid; gap: var(--space-4); place-items: center; padding: var(--space-12) 0; }
.me-empty-cta { text-align: center; }

/* === HERO === */
.me-hero {
  position: relative; overflow: hidden;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--blue-700) 0%, var(--blue-500) 60%, var(--coral) 130%);
  color: #fff;
  padding: var(--space-7);
  box-shadow: var(--shadow-poster);
}
.me-hero-bg {
  position: absolute; inset: 0;
  background: var(--halftone);
  opacity: 0.18;
  mix-blend-mode: screen;
  pointer-events: none;
}
.me-hero-inner {
  position: relative; z-index: 1;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--space-6);
  align-items: center;
}
@media (max-width: 768px) {
  .me-hero-inner { grid-template-columns: 1fr; }
}

.me-hero-left .kicker {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 12px; color: rgba(255,255,255,0.85);
}
.me-hero-left .kicker::before { content: ""; width: 22px; height: 2px; background: var(--lemon); }
.me-hero-left h1 {
  margin: 6px 0 8px;
  font-family: var(--font-display); font-weight: 900;
  font-size: clamp(28px, 3.4vw, 40px);
  line-height: 1.05;
}
.me-hero-left p { margin: 0; opacity: 0.92; max-width: 56ch; font-size: 14.5px; }

.me-hero-pills { display: flex; gap: 8px; flex-wrap: wrap; margin-top: var(--space-4); }
.me-hero-pills .pill {
  display: inline-flex; align-items: center;
  padding: 4px 10px;
  border-radius: var(--radius-pill);
  background: rgba(255,255,255,0.15);
  color: #fff;
  font-size: 12px; font-weight: 600;
  font-family: var(--font-mono);
}

.me-hero-right {
  display: grid; grid-template-columns: auto 1fr; gap: var(--space-3); align-items: center;
  background: rgba(255,255,255,0.14);
  border: 1px solid rgba(255,255,255,0.18);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  min-width: 280px;
  backdrop-filter: blur(6px);
}
.me-hero-avatar {
  width: 56px; height: 56px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--lemon), var(--coral));
  display: grid; place-items: center;
  color: var(--ink-900);
  font-family: var(--font-display); font-weight: 800; font-size: 22px;
  border: 2px solid #fff;
  overflow: hidden;
}
.me-hero-avatar img { width: 100%; height: 100%; object-fit: cover; }
.me-hero-meta { display: grid; gap: 2px; min-width: 0; }
.me-hero-meta strong {
  font-family: var(--font-display); font-weight: 900;
  font-size: 16px; color: #fff;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.me-hero-meta small {
  font-family: var(--font-mono); font-size: 11px;
  color: rgba(255,255,255,0.78);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.me-hero-actions { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
.me-hero-actions .btn { background: rgba(255,255,255,0.92); color: var(--blue-700); border-color: transparent; font-size: 12px; padding: 6px 12px; }
.me-hero-actions .btn:hover { background: #fff; color: var(--ink-900); transform: translate(-1px, -1px); box-shadow: var(--shadow-poster-soft); }
.me-hero-actions .btn-ghost { background: transparent; color: rgba(255,255,255,0.92); }
.me-hero-actions .btn-ghost:hover { background: rgba(255,255,255,0.18); color: #fff; }

.me-token-card {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-5);
  background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(240,247,255,0.94));
  border: 1.5px solid var(--blue-200);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
}

.me-token-card h2 {
  margin: 6px 0 8px;
  font-family: var(--font-display);
  font-size: 24px;
  line-height: 1.1;
}

.me-token-card p {
  margin: 0;
  color: var(--ink-500);
  font-size: 13px;
  line-height: 1.7;
}

.me-token-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.me-token-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.me-token-preview,
.me-token-used {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--ink-500);
}

.me-token-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.me-token-secret {
  display: grid;
  gap: 10px;
  padding: var(--space-4);
  background: var(--ink-900);
  color: #fff;
  border-radius: var(--radius-sm);
}

.me-token-secret span {
  font-family: var(--font-brand);
  letter-spacing: var(--letter-kicker);
  font-size: 11px;
  color: rgba(255,255,255,0.72);
}

.me-token-secret code {
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: 12px;
  white-space: nowrap;
  background: transparent;
  color: #fff;
}

/* === SUBSCRIPTIONS & FOLLOWS === */
.me-sub-follow-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-5);
  align-items: flex-start;
}
@media (max-width: 900px) {
  .me-sub-follow-grid { grid-template-columns: 1fr; }
}

.me-sub-card {
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  padding: var(--space-5);
  display: grid; gap: var(--space-4);
}

.me-sub-list {
  display: grid; gap: 6px;
  max-height: 420px;
  overflow-y: auto;
  scrollbar-width: thin;
}

.me-sub-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 10px;
  align-items: center;
  padding: 10px;
  background: var(--surface-soft);
  border-radius: var(--radius-sm);
}

.me-sub-row-icon {
  width: 36px; height: 36px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--blue-500), var(--blue-700));
  color: var(--ink-on-blue);
  display: grid; place-items: center;
  font-family: var(--font-display); font-weight: 800; font-size: 15px;
  flex: 0 0 auto;
  overflow: hidden;
}
.me-sub-row-icon img { width: 100%; height: 100%; object-fit: cover; }

.me-sub-row-info {
  display: grid; gap: 2px;
  min-width: 0;
}

.me-sub-row-head {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}

.me-sub-row-name {
  font-size: 13.5px; font-weight: 700; color: var(--ink-900);
  text-decoration: none;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.me-sub-row-name:hover { color: var(--blue-700); text-decoration: underline; }

.me-sub-row-meta {
  font-family: var(--font-mono); font-size: 11px; color: var(--ink-500);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* === LAYOUT === */
.me-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: var(--space-5);
  align-items: flex-start;
}
@media (max-width: 1023px) {
  .me-layout { grid-template-columns: 1fr; }
}

/* Plugin sidebar */
.me-plugin-list {
  position: sticky;
  top: calc(var(--topbar-h) + var(--space-4));
  align-self: flex-start;
  display: grid; gap: var(--space-3);
  padding: var(--space-4);
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  max-height: calc(100vh - var(--topbar-h) - var(--space-7));
  overflow-y: auto;
}
@media (max-width: 1023px) {
  .me-plugin-list { position: static; max-height: none; }
}

.me-section-head {
  display: flex; justify-content: space-between; align-items: center; gap: var(--space-3);
}
.me-section-head h2 {
  margin: 0;
  font-family: var(--font-display); font-weight: 900;
  font-size: 18px; line-height: 1.1;
  color: var(--ink-900);
}
.me-section-head small {
  font-family: var(--font-mono); font-size: 11px;
  color: var(--ink-500);
  background: var(--surface-soft);
  padding: 2px 8px; border-radius: var(--radius-pill);
}
.me-section-head .me-section-summary {
  margin: 4px 0 0;
  font-size: 13px; color: var(--ink-500);
}
.me-section-actions { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }

.me-plugin-rail {
  display: grid; gap: 6px;
  max-height: 60vh;
  overflow-y: auto;
  scrollbar-width: thin;
}

.me-plugin-item {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
  align-items: center;
  padding: 10px;
  border-radius: var(--radius-sm);
  text-align: left;
  background: transparent;
  border: 1.5px solid transparent;
  transition: background var(--dur-fast), border-color var(--dur-fast), transform var(--dur-fast);
}
.me-plugin-item:hover { background: var(--surface-hover); }
.me-plugin-item.is-active {
  background: var(--blue-50);
  border-color: var(--blue-300);
}
.me-plugin-item-icon {
  width: 36px; height: 36px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--blue-500), var(--blue-700));
  color: var(--ink-on-blue);
  display: grid; place-items: center;
  font-family: var(--font-display); font-weight: 800; font-size: 15px;
  flex: 0 0 auto;
  overflow: hidden;
}
.me-plugin-item-icon img { width: 100%; height: 100%; object-fit: cover; }
.me-plugin-item-info { display: grid; gap: 2px; min-width: 0; }
.me-plugin-item-info strong {
  font-size: 13.5px; font-weight: 700; color: var(--ink-900);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.me-plugin-item-info small {
  font-family: var(--font-mono); font-size: 11px; color: var(--ink-500);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.me-plugin-item-meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 2px; }
.me-plugin-item-meta .muted { font-family: var(--font-mono); font-size: 11px; color: var(--ink-500); }

/* Main column */
.me-main {
  display: grid; gap: var(--space-5);
  min-width: 0;
}

.me-card {
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  padding: var(--space-5);
  display: grid; gap: var(--space-4);
}

.me-metric-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
}
@media (max-width: 768px) { .me-metric-row { grid-template-columns: repeat(2, 1fr); } }
.me-metric {
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  display: grid; gap: 4px;
}
.me-metric span {
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 11px; color: var(--ink-500); text-transform: uppercase;
}
.me-metric strong {
  font-family: var(--font-brand); letter-spacing: var(--letter-bebas);
  font-size: 28px; color: var(--ink-900); line-height: 1;
}
.me-metric small { font-family: var(--font-mono); font-size: 11.5px; color: var(--ink-500); }

.me-info-grid {
  display: grid; grid-template-columns: 1.4fr 1fr; gap: var(--space-5);
}
@media (max-width: 768px) { .me-info-grid { grid-template-columns: 1fr; } }
.me-info-grid h4 {
  margin: 0 0 8px;
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 11.5px; color: var(--ink-500); text-transform: uppercase;
}
.me-soft-note { margin: 0 0 var(--space-3); font-size: 12.5px; color: var(--ink-500); line-height: 1.55; }

.me-meta-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.me-meta-list li {
  display: grid; grid-template-columns: 80px 1fr; gap: 8px;
  font-size: 13px;
}
.me-meta-list li span { color: var(--ink-500); font-size: 12px; }
.me-meta-list li strong { color: var(--ink-900); font-weight: 600; word-break: break-all; }

/* Versions */
.me-version-list { display: grid; gap: 8px; }
.me-version-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--space-3);
  padding: 10px 12px;
  background: var(--surface-soft);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  align-items: center;
}
.me-version-head {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.me-version-head strong {
  font-family: var(--font-mono); font-size: 13.5px; font-weight: 700; color: var(--ink-900);
}
.me-version-main p {
  margin: 4px 0 2px;
  font-size: 13px; color: var(--ink-700);
}
.me-version-main small {
  font-family: var(--font-mono); font-size: 11px; color: var(--ink-500);
}
.me-version-actions { display: flex; gap: 6px; }

/* Reviews */
.me-review-feed { display: grid; gap: 8px; }
.me-review-item {
  display: grid; grid-template-columns: 1fr auto; gap: var(--space-3);
  align-items: center;
  padding: 10px 12px;
  background: var(--surface-soft);
  border-radius: var(--radius-sm);
}
.me-review-item strong {
  font-family: var(--font-display); font-weight: 700; font-size: 13.5px; color: var(--ink-900);
}
.me-review-item p { margin: 2px 0 0; font-size: 12.5px; color: var(--ink-700); }
.me-review-meta { display: grid; gap: 2px; text-align: right; font-family: var(--font-mono); font-size: 11px; color: var(--ink-500); }

/* Modal */
.me-modal-backdrop {
  position: fixed; inset: 0; z-index: 95;
  display: grid; place-items: center;
  padding: var(--space-5);
  background: var(--overlay-strong);
  backdrop-filter: blur(8px);
}
.me-modal {
  width: min(560px, 100%);
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-3);
  padding: var(--space-6);
  display: grid; gap: var(--space-4);
  position: relative;
}
.me-modal::before {
  content: ""; position: absolute; left: 0; right: 0; top: 0; height: 4px;
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  background: linear-gradient(90deg, var(--blue-500), var(--coral));
}
.me-modal-head {
  display: flex; justify-content: space-between; align-items: center; gap: var(--space-3);
}
.me-modal-head .kicker {
  display: block;
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 11px; color: var(--blue-700); text-transform: uppercase;
}
.me-modal-head h2 {
  margin: 4px 0 0;
  font-family: var(--font-display); font-weight: 900;
  font-size: 22px; line-height: 1.15;
}
.me-modal-body { display: grid; gap: var(--space-3); }
.me-form-field { display: grid; gap: 4px; font-size: 12.5px; color: var(--ink-700); }
.me-form-field span {
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 11px; color: var(--ink-500); text-transform: uppercase;
}
.me-form-field input, .me-form-field select {
  padding: 8px 12px;
  border: 1.5px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--surface);
  font-size: 13px;
}
.me-form-field input:focus, .me-form-field select:focus { outline: none; border-color: var(--blue-500); box-shadow: var(--ring); }

.me-form-icon-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}
.me-form-icon-row input { width: 100%; }
.me-form-file { display: none; }
.me-form-hint {
  margin: 4px 0 0;
  font-size: 11px; color: var(--ink-500);
  line-height: 1.45;
}
.me-modal-foot { display: flex; justify-content: flex-end; gap: 8px; }

/* === entry animations === */
[data-anim] { animation: fade-up var(--dur-slow) var(--ease-emphasized) both; }
[data-anim="enter-1"] { animation-delay: 60ms; }
[data-anim="enter-2"] { animation-delay: 160ms; }
@keyframes fade-up {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  [data-anim] { animation: none; }
}
</style>
