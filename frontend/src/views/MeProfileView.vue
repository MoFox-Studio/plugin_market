<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import api from '@/api'
import type { AuthorProfile, PinnedPlugin, Plugin } from '@/types'
import EmptyState from '@/components/EmptyState.vue'
import BioEditor from '@/components/BioEditor.vue'
import BackgroundUploader from '@/components/BackgroundUploader.vue'
import PinnedPluginEditor from '@/components/PinnedPluginEditor.vue'

const auth = useAuthStore()
const toast = useToastStore()

const loading = ref(true)
const profile = ref<AuthorProfile | null>(null)
const plugins = ref<Plugin[]>([])
const bioDraft = ref('')
const backgroundDraft = ref<string | null>(null)
const pins = ref<PinnedPlugin[]>([])
const savingProfile = ref(false)
const pinsBusy = ref(false)

async function loadPage(): Promise<void> {
  const [profileResult, pinResult, pluginResult] = await Promise.all([
    api.me.profile.get().catch(() => null),
    api.me.pins.list().catch(() => []),
    api.get('/api/v1/me/plugins').catch(() => ({ items: [] })),
  ])
  profile.value = profileResult
  bioDraft.value = profileResult?.bio || ''
  backgroundDraft.value = profileResult?.background_image_url || null
  pins.value = pinResult
  plugins.value = pluginResult.items || []
}

async function saveProfile() {
  if (bioDraft.value.length > 2000) {
    toast.show('Bio 不能超过 2000 字', 'error')
    return
  }
  if (backgroundDraft.value
      && !/^https:\/\//i.test(backgroundDraft.value)
      && !backgroundDraft.value.startsWith('/plugin-media/')) {
    toast.show('背景图请使用 https 链接，或直接上传文件', 'error')
    return
  }
  savingProfile.value = true
  try {
    profile.value = await api.me.profile.update({
      bio: bioDraft.value,
      // 后端用 None 表示"不修改"、空字符串表示"清空"，所以这里把 null 标记成空串
      background_image_url: backgroundDraft.value === null ? '' : backgroundDraft.value,
    })
    toast.show('个人空间资料已保存', 'ok')
  } catch (e) {
    toast.show((e as Error).message || '保存失败', 'error')
  } finally {
    savingProfile.value = false
  }
}

async function addPin(payload: { pluginId: string; reason: string | null }) {
  pinsBusy.value = true
  try {
    await api.me.pins.add({ plugin_id: payload.pluginId, pinned_reason: payload.reason })
    pins.value = await api.me.pins.list()
    toast.show('已新增置顶作品', 'ok')
  } catch (e) {
    toast.show((e as Error).message || '新增置顶失败', 'error')
  } finally {
    pinsBusy.value = false
  }
}

async function resetPinReason(payload: { pluginId: string; reason: string | null }) {
  pinsBusy.value = true
  try {
    await api.me.pins.update(payload.pluginId, { pinned_reason: payload.reason })
    pins.value = await api.me.pins.list()
    toast.show('已重置置顶理由', 'ok')
  } catch (e) {
    toast.show((e as Error).message || '更新失败', 'error')
  } finally {
    pinsBusy.value = false
  }
}

async function removePin(pluginId: string) {
  pinsBusy.value = true
  try {
    await api.me.pins.remove(pluginId)
    pins.value = await api.me.pins.list()
    toast.show('已取消置顶', 'ok')
  } catch (e) {
    toast.show((e as Error).message || '取消置顶失败', 'error')
  } finally {
    pinsBusy.value = false
  }
}

onMounted(async () => {
  loading.value = true
  await loadPage()
  loading.value = false
})
</script>

<template>
  <div class="profile-page" v-if="!auth.isAuthenticated">
    <div class="profile-empty">
      <EmptyState title="请先登录" message="登录后才能编辑公开资料和置顶作品。" />
      <a class="btn btn-primary" :href="auth.getLoginUrl('/me/profile')">GitHub 登录</a>
    </div>
  </div>

  <div class="profile-page" v-else>
    <header class="profile-hero" data-anim="enter-1">
      <div class="profile-hero-bg" aria-hidden="true"></div>
      <div class="profile-hero-inner">
        <div>
          <span class="kicker">PROFILE SPACE</span>
          <h1>个人空间设置</h1>
          <p>这里只管 Bio、背景图、置顶作品三件事，不会和插件治理混在一起。</p>
        </div>
        <div class="profile-hero-actions">
          <router-link class="btn btn-ghost btn-sm" :to="{ name: 'me' }">← 回到工作台</router-link>
          <router-link
            v-if="profile"
            class="btn btn-sm"
            :to="`/author/${encodeURIComponent(profile.author_id)}`"
            target="_blank"
          >预览公开主页 ↗</router-link>
        </div>
      </div>
    </header>

    <div class="profile-layout" data-anim="enter-2">
      <!-- 左：资料编辑 -->
      <section class="profile-card">
        <div class="profile-card-head">
          <div>
            <span class="kicker">EDIT</span>
            <h2>资料</h2>
            <p>这些资料会展示在公开主页 <code>/author/&lt;id&gt;</code>。</p>
          </div>
          <button
            class="btn btn-primary btn-sm"
            :disabled="savingProfile || loading"
            @click="saveProfile"
          >{{ savingProfile ? '保存中…' : '保存资料' }}</button>
        </div>

        <div class="profile-block">
          <div class="profile-block-head">
            <span class="profile-block-label">个人简介 (Bio)</span>
            <small>不超过 2000 字，支持轻量 markdown</small>
          </div>
          <BioEditor v-model="bioDraft" :disabled="savingProfile || loading" />
        </div>

        <div class="profile-block">
          <div class="profile-block-head">
            <span class="profile-block-label">个人空间背景图</span>
            <small>仅支持 https 直链 · 留空使用默认渐变</small>
          </div>
          <BackgroundUploader v-model="backgroundDraft" :disabled="savingProfile || loading" />
        </div>
      </section>

      <!-- 右：置顶作品 -->
      <section class="profile-card">
        <div class="profile-card-head">
          <div>
            <span class="kicker">PINNED</span>
            <h2>置顶作品</h2>
            <p>最多 6 件，会优先展示在你的公开主页。可以为每件作品写一句话推荐理由。</p>
          </div>
        </div>

        <div class="profile-block">
          <PinnedPluginEditor
            :pins="pins"
            :available-plugins="plugins"
            :busy="pinsBusy"
            @add="addPin"
            @update-reason="resetPinReason"
            @remove="removePin"
          />
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.profile-page {
  width: min(var(--shell-max), 100%);
  margin: 0 auto;
  padding: var(--space-7) var(--space-7) var(--space-16);
  display: grid;
  gap: var(--space-7);
}
@media (max-width: 768px) {
  .profile-page { padding: var(--space-5) var(--space-4) var(--space-12); }
}

.profile-empty {
  display: grid; gap: var(--space-4); place-items: center;
  padding: var(--space-12) 0;
}

/* HERO */
.profile-hero {
  position: relative; overflow: hidden;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--blue-700) 0%, var(--blue-500) 60%, #5fb8ff 110%);
  color: #fff;
  padding: var(--space-7);
  box-shadow: var(--shadow-poster);
}
.profile-hero-bg {
  position: absolute; inset: 0;
  background: var(--halftone);
  opacity: 0.18; mix-blend-mode: screen;
  pointer-events: none;
}
.profile-hero-inner {
  position: relative; z-index: 1;
  display: flex; justify-content: space-between; align-items: center;
  gap: var(--space-5); flex-wrap: wrap;
}
.profile-hero .kicker {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 12px; color: rgba(255,255,255,0.92);
}
.profile-hero .kicker::before { content: ""; width: 22px; height: 2px; background: var(--lemon); }
.profile-hero h1 {
  margin: 6px 0 8px;
  font-family: var(--font-display); font-weight: 900;
  font-size: clamp(28px, 3.4vw, 40px);
  line-height: 1.05;
}
.profile-hero p { margin: 0; opacity: 0.92; max-width: 56ch; font-size: 14.5px; }
.profile-hero-actions { display: flex; gap: 8px; }
.profile-hero-actions .btn {
  background: rgba(255,255,255,0.92);
  color: var(--blue-700);
  border-color: transparent;
}
.profile-hero-actions .btn:hover {
  background: #fff; color: var(--ink-900);
  transform: translate(-1px, -1px);
  box-shadow: var(--shadow-poster-soft);
}
.profile-hero-actions .btn-ghost {
  background: transparent; color: rgba(255,255,255,0.92);
  border-color: rgba(255,255,255,0.4);
}
.profile-hero-actions .btn-ghost:hover {
  background: rgba(255,255,255,0.16); color: #fff;
  border-color: rgba(255,255,255,0.6);
}

/* LAYOUT */
.profile-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: var(--space-5);
  align-items: flex-start;
}
@media (max-width: 1023px) {
  .profile-layout { grid-template-columns: 1fr; }
}

.profile-card {
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  padding: var(--space-5);
  display: grid; gap: var(--space-5);
}

.profile-card-head {
  display: flex; justify-content: space-between; align-items: flex-end;
  gap: var(--space-3); flex-wrap: wrap;
}
.profile-card-head .kicker {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 11px; color: var(--blue-700);
}
.profile-card-head .kicker::before { content: ""; width: 16px; height: 2px; background: var(--coral); }
.profile-card-head h2 {
  margin: 6px 0 4px;
  font-family: var(--font-display); font-weight: 900;
  font-size: 20px; line-height: 1.15;
  color: var(--ink-900);
}
.profile-card-head p {
  margin: 0;
  color: var(--ink-500); font-size: 12.5px;
}
.profile-card-head code {
  background: var(--surface-soft); padding: 1px 5px;
  border-radius: var(--radius-xs);
  font-family: var(--font-mono); font-size: 11.5px;
  color: var(--ink-700);
}

.profile-block {
  display: grid; gap: 8px;
}
.profile-block-head {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: var(--space-3); flex-wrap: wrap;
}
.profile-block-label {
  font-family: var(--font-brand); letter-spacing: var(--letter-kicker);
  font-size: 11.5px; color: var(--ink-700);
  text-transform: uppercase;
}
.profile-block-head small {
  font-family: var(--font-mono); font-size: 11px; color: var(--ink-500);
}

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
