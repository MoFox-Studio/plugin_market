<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import type { Skill, SkillVersion, SkillComment } from '@/types'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()

const skillId = computed(() => route.params.id as string)

const skill = ref<Skill | null>(null)
const versions = ref<SkillVersion[]>([])
const comments = ref<SkillComment[]>([])
const loading = ref(true)
const rating = ref<{ distribution?: Record<string, number>; viewer_rating?: number }>({})
const likeBusy = ref(false)

const commentText = ref('')
const commentBusy = ref(false)

const latestVersion = computed(() => versions.value[0] || null)
const downloadUrl = computed(() =>
  latestVersion.value
    ? api.skills.downloadUrl(skillId.value, latestVersion.value.version)
    : ''
)

async function loadSkill() {
  loading.value = true
  try {
    const [s, v, c, r] = await Promise.all([
      api.skills.get(skillId.value),
      api.skills.versions(skillId.value).then(r => r.items).catch(() => []),
      api.skills.comments(skillId.value).then(r => r.items).catch(() => []),
      api.skills.rating(skillId.value).catch(() => ({})),
    ])
    skill.value = s
    versions.value = v
    comments.value = c
    rating.value = r
  } catch {
    toast.show('Skill 不存在', 'error')
    router.push({ name: 'skills' })
  } finally {
    loading.value = false
  }
}

async function toggleLike() {
  if (!auth.viewer) { toast.show('请先登录', 'error'); return }
  if (!skill.value) return
  likeBusy.value = true
  try {
    await api.skills.toggleLike(skillId.value)
    skill.value = await api.skills.get(skillId.value)
  } catch (e) {
    toast.show((e as Error).message || '操作失败', 'error')
  } finally {
    likeBusy.value = false
  }
}

async function postRating(score: number) {
  if (!auth.viewer) { toast.show('请先登录', 'error'); return }
  try {
    await api.skills.postRating(skillId.value, score)
    rating.value = await api.skills.rating(skillId.value)
    toast.show('评分成功', 'ok')
  } catch (e) {
    toast.show((e as Error).message || '评分失败', 'error')
  }
}

async function postComment() {
  if (!auth.viewer) { toast.show('请先登录', 'error'); return }
  if (!commentText.value.trim()) return
  commentBusy.value = true
  try {
    const c = await api.skills.postComment(skillId.value, { content: commentText.value })
    comments.value.push(c)
    commentText.value = ''
    toast.show('评论发布成功', 'ok')
  } catch (e) {
    toast.show((e as Error).message || '评论失败', 'error')
  } finally {
    commentBusy.value = false
  }
}

async function recordDownload() {
  try {
    await api.skills.recordInstall(skillId.value)
  } catch { /* silent */ }
}

onMounted(loadSkill)
</script>

<template>
  <div v-if="loading" class="skill-loading">加载中…</div>

  <div v-else-if="skill" class="skill-page">
    <!-- header -->
    <header class="skill-hero">
      <div class="skill-hero-icon">
        <img v-if="skill.icon_url" :src="skill.icon_url" :alt="skill.display_name">
        <span v-else>{{ skill.display_name[0]?.toUpperCase() || '?' }}</span>
      </div>
      <div class="skill-hero-info">
        <h1>{{ skill.display_name }}</h1>
        <p class="skill-hero-author">
          作者
          <router-link :to="`/author/${encodeURIComponent(skill.owner_id)}`">
            {{ skill.owner_display_name || skill.owner_login || skill.owner_id }}
          </router-link>
        </p>
        <div class="skill-hero-meta">
          <span v-if="skill.latest_version" class="badge">v{{ skill.latest_version }}</span>
          <span>⭐ {{ skill.rating_avg?.toFixed(1) || '-' }}</span>
          <span>⬇ {{ skill.download_count }} 下载</span>
          <span>💬 {{ skill.comments_count }} 评论</span>
        </div>
      </div>
      <div class="skill-hero-actions">
        <a
          v-if="downloadUrl"
          :href="downloadUrl"
          class="btn btn-primary"
          @click="recordDownload"
        >下载最新版本</a>
        <button
          class="btn"
          :class="{ 'btn-primary': skill.viewer_has_liked }"
          :disabled="likeBusy"
          @click="toggleLike"
        >{{ skill.viewer_has_liked ? '❤️ 已赞' : '🤍 点赞' }} {{ skill.likes_count }}</button>
      </div>
    </header>

    <!-- SKILL.md preview -->
    <section class="skill-section">
      <h2>SKILL.md 预览</h2>
      <pre class="skill-desc">{{ skill.readme_markdown || skill.description }}</pre>
    </section>

    <!-- versions -->
    <section v-if="versions.length" class="skill-section">
      <h2>版本历史（{{ versions.length }}）</h2>
      <div class="skill-version-list">
        <div v-for="v in versions" :key="v.version" class="skill-version-row">
          <div class="skill-version-info">
            <strong>v{{ v.version }}</strong>
            <small>{{ v.created_at }}</small>
            <small v-if="v.package_size">{{ (v.package_size / 1024).toFixed(1) }} KB</small>
          </div>
          <p v-if="v.release_notes" class="skill-version-notes">{{ v.release_notes }}</p>
          <a
            :href="api.skills.downloadUrl(skillId, v.version)"
            class="btn btn-sm"
            @click="recordDownload"
          >下载</a>
        </div>
      </div>
    </section>

    <!-- rating -->
    <section class="skill-section">
      <h2>评分</h2>
      <div class="skill-rating-row">
        <span v-if="rating.viewer_rating" class="skill-rating-my">
          我的评分：{{ '⭐'.repeat(rating.viewer_rating) }}
        </span>
        <div class="skill-rating-stars">
          <button
            v-for="s in 5"
            :key="s"
            class="skill-star-btn"
            :class="{ active: rating.viewer_rating && rating.viewer_rating >= s }"
            :title="`${s} 星`"
            @click="postRating(s)"
          >{{ '⭐' }}</button>
        </div>
      </div>
      <div v-if="rating.distribution" class="skill-rating-dist">
        <div v-for="(count, score) in rating.distribution" :key="score" class="skill-rating-bar">
          <span>{{ score }}★</span>
          <div class="bar-track"><div class="bar-fill" :style="{ width: `${Math.max(1, Number(count) * 10)}%` }"></div></div>
          <span>{{ count }}</span>
        </div>
      </div>
    </section>

    <!-- comments -->
    <section class="skill-section">
      <h2>评论（{{ comments.length }}）</h2>

      <div v-if="auth.viewer" class="skill-comment-form">
        <textarea
          v-model="commentText"
          placeholder="写下你的评论…"
          rows="3"
          maxlength="2000"
        ></textarea>
        <button class="btn btn-primary btn-sm" :disabled="commentBusy || !commentText.trim()" @click="postComment">
          {{ commentBusy ? '发布中…' : '发布评论' }}
        </button>
      </div>
      <p v-else class="skill-comment-login">
        <a :href="`/api/v1/auth/github/login?redirect_to=/skill/${encodeURIComponent(skillId)}`">登录</a> 后可以评论
      </p>

      <div v-if="comments.length" class="skill-comment-list">
        <div v-for="c in comments" :key="c.id" class="skill-comment-item">
          <div class="skill-comment-head">
            <strong>{{ c.author.display_name }}</strong>
            <small>{{ c.created_at }}</small>
          </div>
          <p class="skill-comment-body">{{ c.is_deleted ? '[已删除]' : c.content }}</p>
        </div>
      </div>
      <p v-else class="skill-empty">暂无评论</p>
    </section>
  </div>
</template>

<style scoped>
.skill-page {
  width: min(900px, 100%);
  margin: 0 auto;
  padding: var(--space-6) var(--space-7) var(--space-16);
  display: grid; gap: var(--space-6);
}
.skill-loading { text-align: center; padding: var(--space-12) 0; color: var(--ink-500); }

.skill-hero {
  display: flex; gap: var(--space-4); flex-wrap: wrap;
  align-items: center;
  padding: var(--space-5);
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-lg);
}
.skill-hero-icon {
  width: 72px; height: 72px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--coral), var(--lemon));
  display: grid; place-items: center;
  font-family: var(--font-display); font-weight: 900; font-size: 28px;
  color: var(--ink-900);
  overflow: hidden;
  flex-shrink: 0;
}
.skill-hero-icon img { width: 100%; height: 100%; object-fit: cover; }
.skill-hero-info { flex: 1; min-width: 0; }
.skill-hero-info h1 {
  margin: 0;
  font-family: var(--font-display); font-weight: 900; font-size: 28px; line-height: 1.1;
}
.skill-hero-author { margin: 4px 0 0; font-size: 13px; color: var(--ink-500); }
.skill-hero-author a { color: var(--blue-600); text-decoration: none; }
.skill-hero-author a:hover { text-decoration: underline; }
.skill-hero-meta { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 8px; font-size: 13px; color: var(--ink-600); }
.skill-hero-actions { display: flex; gap: 8px; flex-shrink: 0; }

.skill-section {
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  padding: var(--space-5);
}
.skill-section h2 {
  margin: 0 0 var(--space-3);
  font-family: var(--font-display); font-weight: 900; font-size: 18px;
}

.skill-desc {
  margin: 0;
  font-size: 13.5px; line-height: 1.7; color: var(--ink-700);
  white-space: pre-wrap; word-break: break-word;
  font-family: inherit;
  background: var(--surface-soft);
  padding: var(--space-4);
  border-radius: var(--radius-sm);
}

.skill-version-list { display: grid; gap: 8px; }
.skill-version-row {
  display: flex; gap: var(--space-3); align-items: center; flex-wrap: wrap;
  padding: 10px 12px;
  background: var(--surface-soft);
  border-radius: var(--radius-sm);
}
.skill-version-info { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.skill-version-info strong { font-family: var(--font-mono); font-size: 14px; }
.skill-version-info small { color: var(--ink-500); font-size: 12px; }
.skill-version-notes { flex: 1; margin: 0; font-size: 12.5px; color: var(--ink-600); min-width: 200px; }

.skill-rating-row { display: flex; gap: var(--space-4); align-items: center; flex-wrap: wrap; }
.skill-rating-my { font-size: 13px; color: var(--ink-600); }
.skill-rating-stars { display: flex; gap: 4px; }
.skill-star-btn { background: none; border: none; font-size: 22px; cursor: pointer; opacity: 0.3; padding: 2px; }
.skill-star-btn.active, .skill-star-btn:hover { opacity: 1; }

.skill-rating-dist { display: grid; gap: 6px; margin-top: var(--space-3); max-width: 300px; }
.skill-rating-bar { display: grid; grid-template-columns: 30px 1fr 30px; gap: 8px; align-items: center; font-size: 12px; color: var(--ink-600); }
.bar-track { height: 8px; background: var(--surface-soft); border-radius: 4px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--lemon); border-radius: 4px; }

.skill-comment-form { display: grid; gap: 8px; }
.skill-comment-form textarea {
  padding: 10px 12px;
  border: 1.5px solid var(--line);
  border-radius: var(--radius-sm);
  font-size: 13px; resize: vertical;
  background: var(--surface);
  font-family: inherit;
}
.skill-comment-form textarea:focus { outline: none; border-color: var(--blue-500); box-shadow: var(--ring); }
.skill-comment-login { font-size: 13px; color: var(--ink-500); }
.skill-comment-login a { color: var(--blue-600); }

.skill-comment-list { display: grid; gap: 8px; margin-top: var(--space-3); }
.skill-comment-item {
  padding: 10px 12px;
  background: var(--surface-soft);
  border-radius: var(--radius-sm);
}
.skill-comment-head { display: flex; gap: 8px; align-items: center; margin-bottom: 4px; }
.skill-comment-head strong { font-size: 13px; }
.skill-comment-head small { font-family: var(--font-mono); font-size: 11px; color: var(--ink-500); }
.skill-comment-body { margin: 0; font-size: 13px; line-height: 1.6; color: var(--ink-700); }
.skill-empty { font-size: 13px; color: var(--ink-500); }
</style>
