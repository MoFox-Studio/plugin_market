<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { useToastStore } from '@/stores/toast';
import api from '@/api';
import type { AuthorProfile, PinnedPlugin, Plugin } from '@/types';
import BioEditor from '@/components/BioEditor.vue';
import BackgroundUploader from '@/components/BackgroundUploader.vue';
import PinnedPluginEditor from '@/components/PinnedPluginEditor.vue';
import PageSkeleton from '@/components/PageSkeleton.vue';
const auth = useAuthStore();
const toast = useToastStore();
const authChecking = ref(true);
const loading = ref(false);
const error = ref('');
const profile = ref<AuthorProfile | null>(null);
const plugins = ref<Plugin[]>([]);
const bioDraft = ref('');
const backgroundDraft = ref<string | null>(null);
const pins = ref<PinnedPlugin[]>([]);
const savingProfile = ref(false);
const uploadingBackground = ref(false);
const pinsBusy = ref(false);
let task = 0;
async function loadPage() {
  if (!auth.isAuthenticated) return;
  const version = ++task;
  loading.value = true;
  error.value = '';
  try {
    const [nextProfile, nextPins, nextPlugins] = await Promise.all([
      api.me.profile.get(),
      api.me.pins.list(),
      api.get('/api/v1/me/plugins'),
    ]);
    if (version !== task) return;
    profile.value = nextProfile;
    bioDraft.value = nextProfile.bio || '';
    backgroundDraft.value = nextProfile.background_image_url || null;
    pins.value = nextPins;
    plugins.value = nextPlugins.items || [];
  } catch (err) {
    if (version === task)
      error.value = (err as Error).message || '无法读取个人档案';
  } finally {
    if (version === task) loading.value = false;
  }
}
async function saveProfile() {
  if (savingProfile.value || uploadingBackground.value || !profile.value)
    return;
  if (bioDraft.value.length > 2000) {
    toast.show('个人简介不能超过 2000 字', 'error');
    return;
  }
  if (
    backgroundDraft.value &&
    !/^https:\/\//i.test(backgroundDraft.value) &&
    !backgroundDraft.value.startsWith('/plugin-media/')
  ) {
    toast.show('请使用 HTTPS 图片地址或直接上传文件', 'error');
    return;
  }
  const version = task;
  savingProfile.value = true;
  try {
    const result = await api.me.profile.update({
      bio: bioDraft.value,
      background_image_url: backgroundDraft.value ?? '',
    });
    if (version !== task) return;
    profile.value = result;
    toast.show('个人档案已保存', 'ok');
  } catch (err) {
    if (version === task)
      toast.show((err as Error).message || '保存失败', 'error');
  } finally {
    if (version === task) savingProfile.value = false;
  }
}
async function updatePins(action: () => Promise<unknown>) {
  if (pinsBusy.value) return;
  const version = task;
  pinsBusy.value = true;
  try {
    await action();
    if (version !== task) return;
    const result = await api.me.pins.list();
    if (version !== task) return;
    pins.value = result;
    toast.show('代表作品已更新', 'ok');
  } catch (err) {
    if (version === task)
      toast.show((err as Error).message || '更新失败', 'error');
  } finally {
    if (version === task) pinsBusy.value = false;
  }
}
const addPin = (payload: { pluginId: string; reason: string | null }) =>
  updatePins(() =>
    api.me.pins.add({
      plugin_id: payload.pluginId,
      pinned_reason: payload.reason,
    }),
  );
const resetPinReason = (payload: { pluginId: string; reason: string | null }) =>
  updatePins(() =>
    api.me.pins.update(payload.pluginId, { pinned_reason: payload.reason }),
  );
const removePin = (id: string) => updatePins(() => api.me.pins.remove(id));
watch(
  () => auth.viewer?.author_id,
  (id) => {
    ++task;
    profile.value = null;
    pins.value = [];
    plugins.value = [];
    bioDraft.value = '';
    backgroundDraft.value = null;
    savingProfile.value = false;
    uploadingBackground.value = false;
    pinsBusy.value = false;
    loading.value = false;
    error.value = '';
    if (id) void loadPage();
  },
  { immediate: true },
);
onMounted(async () => {
  await auth.loadViewer();
  authChecking.value = false;
});
onBeforeUnmount(() => {
  ++task;
});
</script>
<template>
  <div class="page-wrap profile-page">
    <header class="profile-heading">
      <div class="profile-running"><b>人物栏</b><span>公开资料编辑</span></div>
      <div class="profile-title">
        <h1>创作者档案</h1>
        <p v-if="auth.viewer">署名 · {{ auth.viewer.display_name }} <span>@{{ auth.viewer.github_login }}</span></p>
        <p v-else>一份公开的作者介绍，由简介、背景和代表作品组成。</p>
      </div>
      <RouterLink class="btn" to="/me">← 返回工作台</RouterLink>
    </header>
    <PageSkeleton
      v-if="authChecking || auth.loading || loading"
      type="detail"
      :count="3"
    />
    <section v-else-if="auth.error" class="profile-error" role="alert">
      <h2>暂时无法确认登录状态</h2>
      <p>{{ auth.error }}</p>
      <button class="btn" @click="auth.loadViewer(true)">重新连接</button>
    </section>
    <section v-else-if="!auth.isAuthenticated" class="access-panel">
      <div class="profile-entry">
        <span class="eyebrow">编辑入口</span>
        <h2>登录后编辑署名页</h2>
        <p>用自己的 GitHub 账号登录，写下简介，选出希望读者先看到的插件。</p>
        <a class="btn btn-primary" :href="auth.getLoginUrl('/me/profile')">使用 GitHub 登录 ↗</a>
      </div>
      <aside class="profile-colophon" aria-label="公开资料说明">
        <h3>公开主页的构成</h3>
        <dl><div><dt>简介</dt><dd>最多 2,000 字，支持轻量 Markdown</dd></div>
          <div><dt>背景</dt><dd>上传图片或填写 HTTPS 图片地址</dd></div>
          <div><dt>作品选</dt><dd>最多 6 个插件，可附推荐理由</dd></div></dl>
      </aside>
    </section>
    <section v-else-if="error" class="profile-error" role="status">
      <h2>档案暂时无法读取</h2>
      <p>{{ error }}</p>
      <button class="btn" @click="loadPage">重新加载</button>
    </section>
    <div v-else class="profile-layout">
      <form class="profile-card" @submit.prevent="saveProfile">
        <header class="card-head">
          <span class="section-number">主栏</span>
          <div>
            <h2>公开资料</h2>
            <p>让其他人了解你的方向与作品。</p>
          </div>
          <RouterLink
            v-if="profile"
            :to="`/author/${encodeURIComponent(profile.author_id)}`"
            class="preview-link"
            target="_blank"
            rel="noopener"
            >预览 ↗</RouterLink
          >
        </header>
        <div class="profile-block">
          <h3>个人简介</h3>
          <p class="field-note">支持轻量 Markdown，最多 2000 字。</p>
          <BioEditor v-model="bioDraft" :disabled="savingProfile" />
        </div>
        <div class="profile-block">
          <h3>档案背景</h3>
          <p class="field-note">上传一张图片，或粘贴 HTTPS 图片地址。</p>
          <BackgroundUploader
            v-model="backgroundDraft"
            :disabled="savingProfile"
            @busy-change="uploadingBackground = $event"
          />
        </div>
        <footer class="profile-actions">
          <small>简介与链接修改后请保存；图片上传后立即生效。</small
          ><button
            type="submit"
            class="btn btn-primary"
            :disabled="savingProfile || uploadingBackground"
          >
            {{ savingProfile ? '正在保存…' : '保存资料' }}
          </button>
        </footer>
      </form>
      <section class="profile-card pinned-card">
        <header class="card-head">
          <span class="section-number">副栏</span>
          <div>
            <h2>代表作品</h2>
            <p>挑选最多 6 个插件，写下你的推荐理由。</p>
          </div>
        </header>
        <PinnedPluginEditor
          :pins="pins"
          :available-plugins="plugins"
          :busy="pinsBusy"
          @add="addPin"
          @update-reason="resetPinReason"
          @remove="removePin"
        />
        <p class="pin-note">代表作品的变更会立即保存。</p>
      </section>
    </div>
  </div>
</template>
<style scoped>
.profile-page {
  display: grid;
  gap: 28px;
}
.profile-heading {
  display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: end;
  gap: 20px; padding-bottom: 24px; border-bottom: 1px solid var(--ink-700);
}
.profile-running {
  grid-column: 1 / -1; display: flex; gap: 12px; align-items: center;
  padding: 8px 0; border-top: 3px double var(--ink-700); border-bottom: 1px solid var(--line);
  font-size: 11px; letter-spacing: .08em;
}
.profile-running b, .eyebrow { color: var(--blue-700); }
.profile-running span { color: var(--ink-500); }
.eyebrow { font: 11px/1.5 var(--font-mono); letter-spacing: .12em; }
.profile-heading h1 { font: 800 clamp(42px, 5.8vw, 78px)/1.15 var(--font-editorial); letter-spacing: -.055em; margin: 0 0 12px; }
.profile-heading p { margin: 0; color: var(--ink-700); line-height: 1.8; }
.profile-heading p span { margin-left: 6px; font: 12px var(--font-mono); color: var(--ink-500); }
.profile-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(280px, 1fr);
  gap: 24px;
  align-items: start;
}
.profile-card {
  border-top: 2px solid var(--ink-700);
  border-bottom: 1px solid var(--line);
  background: var(--surface);
  padding: 26px;
  min-width: 0;
}
.card-head {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--line);
  margin-bottom: 24px;
}
.section-number {
  color: var(--blue-600);
  font: 13px var(--font-mono);
  padding-top: 3px;
  white-space: nowrap;
}
.card-head h2 {
  font: 800 24px/1.25 var(--font-editorial);
  margin: 0 0 7px;
}
.card-head p {
  font-size: 12px;
  line-height: 1.7;
  color: var(--ink-500);
  margin: 0;
}
.preview-link {
  margin-left: auto;
  white-space: nowrap;
  color: var(--blue-600);
  font-size: 12px;
}
.profile-block {
  margin-top: 28px;
}
.profile-block h3 {
  font-size: 14px;
  margin: 0 0 7px;
}
.field-note,
.pin-note {
  color: var(--ink-500);
  font-size: 12px;
  line-height: 1.7;
}
.field-note {
  margin: 0 0 14px;
}
.pin-note {
  border-top: 1px solid var(--line);
  padding-top: 18px;
  margin: 24px 0 0;
}
.profile-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  border-top: 1px solid var(--line);
  padding-top: 22px;
  margin-top: 28px;
}
.profile-actions small {
  color: var(--ink-500);
  font-size: 12px;
}
.access-panel { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(230px, .85fr); gap: clamp(24px, 6vw, 80px); border-bottom: 1px solid var(--line-strong); padding-block: 16px 32px; }
.profile-entry { align-self: center; }
.profile-entry h2 { margin: 12px 0; font: 800 clamp(25px, 2.8vw, 38px)/1.3 var(--font-editorial); }
.profile-entry p { max-width: 36em; margin: 0 0 24px; line-height: 1.85; color: var(--ink-700); }
.profile-colophon { padding: 20px; border-top: 2px solid var(--ink-700); background: var(--surface); }
.profile-colophon h3 { margin: 0 0 16px; font: 800 19px/1.3 var(--font-editorial); }
.profile-colophon dl { margin: 0; }
.profile-colophon dl div { display: grid; grid-template-columns: 3.5em 1fr; gap: 12px; border-top: 1px solid var(--line); padding: 11px 0; font-size: 12px; }
.profile-colophon dt { color: var(--blue-700); }
.profile-colophon dd { margin: 0; color: var(--ink-700); line-height: 1.55; }
.profile-error {
  border: 1px solid var(--danger);
  padding: 24px;
  background: var(--danger-soft);
  color: var(--danger-ink);
}
.profile-error h2 {
  font-size: 18px;
}
.profile-error p {
  overflow-wrap: anywhere;
}
@media (max-width: 980px) {
  .profile-layout {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 600px) {
  .profile-heading {
    grid-template-columns: 1fr;
    justify-items: start;
  }
  .profile-running { width: 100%; }
  .access-panel { grid-template-columns: 1fr; }
  .profile-card {
    padding: 20px;
  }
  .profile-actions {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
