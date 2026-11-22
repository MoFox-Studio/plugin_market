<script setup lang="ts">
import { useMarketDialog } from '@/composables/useMarketDialog';
const { confirm: confirmAction, prompt: promptAction } = useMarketDialog();
import MarketSelect from '@/components/MarketSelect.vue';
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue';
import api from '@/api';
import { useAuthStore } from '@/stores/auth';
import { useToastStore } from '@/stores/toast';
import { useTaxonomyStore } from '@/stores/taxonomy';
import {
  formatNumber,
  formatRelative,
  formatDate,
  formatBytes,
  statusText,
  categoryLabel,
  reviewActionText,
  EDITABLE_PLUGIN_CATEGORIES,
} from '@/utils/format';
import type {
  AccessTokenStatus,
  MyFollowItem,
  MySubscriptionItem,
  Plugin,
  PluginMetadataPatch,
  PluginSnapshot,
  Skill,
} from '@/types';
import TrustBadge from '@/components/TrustBadge.vue';
import EmptyState from '@/components/EmptyState.vue';
import PageSkeleton from '@/components/PageSkeleton.vue';

import { useSubscriptionStore } from '@/stores/subscriptions';

const auth = useAuthStore();
const toast = useToastStore();
const taxonomy = useTaxonomyStore();
const subStore = useSubscriptionStore();

const activeTab = ref('plugins');
const authChecking = ref(true);
const sectionErrors = ref<Record<string, string>>({});
const snapshotLoading = ref(false);
let identityVersion = 0;
let snapshotVersion = 0;
const sectionLoading = ref<Record<string, boolean>>({});
const pluginActionBusy = ref(false);
const skillDeleteBusy = ref(false);
const workspaceTabs = [
  { key: 'plugins', label: '我的插件' },
  { key: 'skills', label: '我的 Skills' },
  { key: 'collection', label: '订阅与关注' },
  { key: 'token', label: '访问令牌' },
];
const plugins = ref<Plugin[]>([]);
const selectedId = ref<string | null>(null);
const snapshot = ref<PluginSnapshot | null>(null);
const loading = ref(true);
const selectedPlugin = ref<Plugin | null>(null);
const metadataOpen = ref(false);
const metadataSaving = ref(false);
const metadataDisplayName = ref('');
const metadataIconUrl = ref('');
const metadataCategory = ref('');
const metadataTags = ref('');
const iconFileInput = ref<HTMLInputElement | null>(null);
const iconUploading = ref(false);
const accessToken = ref<AccessTokenStatus | null>(null);
const accessTokenValue = ref('');
const accessTokenBusy = ref(false);

const subscriptions = ref<MySubscriptionItem[]>([]);
const subscriptionsBusy = ref(false);
const follows = ref<MyFollowItem[]>([]);
const followsBusy = ref(false);

// --- skills ---
const mySkills = ref<Skill[]>([]);
const skillsBusy = ref(false);
const skillPublishOpen = ref(false);
const skillPublishSaving = ref(false);
const skillPublishSkillId = ref('');
const skillPublishVersion = ref('0.1.0');
const skillPublishNotes = ref('');
const skillPublishCategory = ref('');
const skillPublishTags = ref('');
const skillAvailableCategories = ref<string[]>([]);
const skillZipInput = ref<HTMLInputElement | null>(null);
const skillZipFile = ref<File | null>(null);

async function copyText(value: string, successMessage: string) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(value);
    } else {
      const ta = document.createElement('textarea');
      ta.value = value;
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      ta.style.top = '-9999px';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const copied = document.execCommand('copy');
      document.body.removeChild(ta);
      if (!copied) throw new Error('Copy failed');
    }
    toast.show(successMessage, 'ok');
  } catch {
    toast.show('复制失败，请检查浏览器权限', 'error');
  }
}

async function loadSection(key: string, request: () => Promise<void>) {
  const owner = identityVersion;
  if (sectionLoading.value[key]) return;
  delete sectionErrors.value[key];
  sectionLoading.value[key] = true;
  try {
    await request();
  } catch (error) {
    if (owner !== identityVersion) return;
    sectionErrors.value[key] =
      (error as Error).message || '暂时无法加载，请重试';
  } finally {
    if (owner === identityVersion) sectionLoading.value[key] = false;
  }
}
async function loadPlugins() {
  const owner = identityVersion;
  await loadSection('plugins', async () => {
    const result = await api.get('/api/v1/me/plugins');
    if (owner !== identityVersion) return;
    plugins.value = result.items || [];
    if (!plugins.value.some((item) => item.plugin_id === selectedId.value))
      selectedId.value = plugins.value[0]?.plugin_id || null;
    await loadSnapshot();
  });
}
async function loadAccessToken() {
  const owner = identityVersion;
  await loadSection('token', async () => {
    const result = await api.me.accessToken.get();
    if (owner === identityVersion) accessToken.value = result;
  });
}
async function loadSnapshot() {
  const version = ++snapshotVersion;
  const owner = identityVersion;
  const id = selectedId.value;
  snapshot.value = null;
  selectedPlugin.value = null;
  delete sectionErrors.value.snapshot;
  if (!id) {
    snapshotLoading.value = false;
    return;
  }
  snapshotLoading.value = true;
  try {
    const result = await api.get(
      `/api/v1/me/plugins/${encodeURIComponent(id)}`,
    );
    if (version !== snapshotVersion || owner !== identityVersion) return;
    snapshot.value = result;
    selectedPlugin.value = result?.plugin || null;
  } catch (error) {
    if (version === snapshotVersion && owner === identityVersion)
      sectionErrors.value.snapshot =
        (error as Error).message || '插件资料加载失败';
  } finally {
    if (version === snapshotVersion && owner === identityVersion)
      snapshotLoading.value = false;
  }
}

async function selectPlugin(id: string) {
  selectedId.value = id;
  await loadSnapshot();
}

function openMetadataEditor() {
  if (!selectedPlugin.value) return;
  metadataDisplayName.value = selectedPlugin.value.display_name || '';
  metadataIconUrl.value = selectedPlugin.value.icon_url || '';
  metadataCategory.value = selectedPlugin.value.categories?.[0] || '';
  metadataTags.value = (selectedPlugin.value.tags || []).join(', ');
  metadataOpen.value = true;
}

function closeMetadataEditor() {
  if (!metadataSaving.value && !iconUploading.value) metadataOpen.value = false;
}

function pickIcon() {
  iconFileInput.value?.click();
}

async function onIconFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (
    !file ||
    !selectedPlugin.value ||
    iconUploading.value ||
    metadataSaving.value
  )
    return;
  if (
    !['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(file.type)
  ) {
    toast.show('请选择 PNG、JPEG、WEBP 或 GIF 图片', 'error');
    return;
  }
  if (file.size > 2 * 1024 * 1024) {
    toast.show('图标不能超过 2 MiB', 'error');
    return;
  }
  const owner = identityVersion;
  const pluginId = selectedPlugin.value.plugin_id;
  iconUploading.value = true;
  try {
    const updated = await api.me.plugins.uploadIcon(pluginId, file);
    if (owner !== identityVersion || selectedId.value !== pluginId) return;
    selectedPlugin.value = updated;
    metadataIconUrl.value = updated.icon_url || '';
    plugins.value = plugins.value.map((plugin) =>
      plugin.plugin_id === updated.plugin_id ? updated : plugin,
    );
    if (snapshot.value) snapshot.value = { ...snapshot.value, plugin: updated };
    toast.show('图标已上传', 'ok');
  } catch (e) {
    if (owner === identityVersion)
      toast.show((e as Error).message || '上传失败', 'error');
  } finally {
    if (owner === identityVersion) iconUploading.value = false;
  }
}

async function saveMetadataPatch() {
  if (!selectedPlugin.value || metadataSaving.value || iconUploading.value)
    return;
  const owner = identityVersion;
  const pluginId = selectedPlugin.value.plugin_id;
  const payload: PluginMetadataPatch = {
    display_name:
      metadataDisplayName.value.trim() || selectedPlugin.value.display_name,
    icon_url: metadataIconUrl.value.trim() || null,
    categories: metadataCategory.value ? [metadataCategory.value] : [],
    tags: metadataTags.value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean),
  };
  metadataSaving.value = true;
  try {
    const updated = await api.me.plugins.patchMetadata(pluginId, payload);
    if (owner !== identityVersion || selectedId.value !== pluginId) return;
    selectedPlugin.value = updated;
    plugins.value = plugins.value.map((plugin) =>
      plugin.plugin_id === updated.plugin_id ? updated : plugin,
    );
    if (snapshot.value) snapshot.value = { ...snapshot.value, plugin: updated };
    metadataOpen.value = false;
    toast.show('插件资料已更新', 'ok');
  } catch (e) {
    if (owner === identityVersion)
      toast.show((e as Error).message || '更新失败', 'error');
  } finally {
    if (owner === identityVersion) metadataSaving.value = false;
  }
}

async function yankVersion(pluginId: string, version: string) {
  if (
    pluginActionBusy.value ||
    !(await confirmAction(`确认下架 ${pluginId}@${version} 吗？`))
  )
    return;
  const reason = await promptAction('可填写下架原因，留空也可以。', '');
  if (reason === null) return;
  const owner = identityVersion;
  pluginActionBusy.value = true;
  try {
    await api.post(
      `/api/v1/me/plugins/${encodeURIComponent(pluginId)}/versions/${encodeURIComponent(version)}/yank`,
      reason.trim() ? { reason: reason.trim() } : {},
    );
    if (owner !== identityVersion) return;
    toast.show('版本已下架', 'ok');
    if (selectedId.value === pluginId) await loadSnapshot();
  } catch (e) {
    if (owner === identityVersion)
      toast.show((e as Error).message || '操作失败', 'error');
  } finally {
    if (owner === identityVersion) pluginActionBusy.value = false;
  }
}
async function deletePlugin(pluginId: string) {
  if (
    pluginActionBusy.value ||
    !(await confirmAction(`确认彻底删除 ${pluginId} 吗？这个操作不可撤销。`))
  )
    return;
  const owner = identityVersion;
  pluginActionBusy.value = true;
  try {
    await api.del(`/api/v1/me/plugins/${encodeURIComponent(pluginId)}`);
    if (owner !== identityVersion) return;
    if (selectedId.value === pluginId) {
      selectedId.value = null;
      snapshot.value = null;
      selectedPlugin.value = null;
    }
    toast.show('插件已删除', 'ok');
    await loadPlugins();
  } catch (e) {
    if (owner === identityVersion)
      toast.show((e as Error).message || '删除失败', 'error');
  } finally {
    if (owner === identityVersion) pluginActionBusy.value = false;
  }
}
async function rotateAccessToken() {
  if (accessTokenBusy.value) return;
  const owner = identityVersion;
  accessTokenBusy.value = true;
  try {
    const rotated = await api.me.accessToken.rotate();
    if (owner !== identityVersion) return;
    accessTokenValue.value = rotated.token;
    await loadAccessToken();
    if (owner === identityVersion)
      toast.show('已生成新访问令牌，旧令牌已失效', 'ok');
  } catch (e) {
    if (owner === identityVersion)
      toast.show((e as Error).message || '生成失败', 'error');
  } finally {
    if (owner === identityVersion) accessTokenBusy.value = false;
  }
}
async function revokeAccessToken() {
  if (
    accessTokenBusy.value ||
    !(await confirmAction(
      '确认撤销当前访问令牌吗？Neo-MoFox 将无法继续从市场同步订阅。',
    ))
  )
    return;
  const owner = identityVersion;
  accessTokenBusy.value = true;
  try {
    const result = await api.me.accessToken.revoke();
    if (owner !== identityVersion) return;
    accessToken.value = result;
    accessTokenValue.value = '';
    toast.show('访问令牌已撤销', 'ok');
  } catch (e) {
    if (owner === identityVersion)
      toast.show((e as Error).message || '撤销失败', 'error');
  } finally {
    if (owner === identityVersion) accessTokenBusy.value = false;
  }
}

async function loadSubscriptions() {
  const owner = identityVersion;
  await loadSection('subscriptions', async () => {
    const result = await api.me.subscriptions();
    if (owner === identityVersion) subscriptions.value = result.items || [];
  });
}
async function loadFollows() {
  const owner = identityVersion;
  await loadSection('follows', async () => {
    const result = await api.me.follows();
    if (owner === identityVersion) follows.value = result.items || [];
  });
}

async function unsubscribe(pluginId: string) {
  if (subscriptionsBusy.value) return;
  const owner = identityVersion;
  subscriptionsBusy.value = true;
  try {
    const result = await api.plugins.toggleSubscription(pluginId);
    if (owner !== identityVersion) return;
    subStore.set(pluginId, result.subscribed);
    if (!result.subscribed)
      subscriptions.value = subscriptions.value.filter(
        (item) => item.plugin_id !== pluginId,
      );
    else await loadSubscriptions();
    toast.show(result.subscribed ? '订阅状态已同步' : '已取消订阅', 'ok');
  } catch (e) {
    if (owner === identityVersion)
      toast.show((e as Error).message || '操作失败', 'error');
  } finally {
    if (owner === identityVersion) subscriptionsBusy.value = false;
  }
}
async function unfollow(authorId: string) {
  if (followsBusy.value) return;
  const owner = identityVersion;
  followsBusy.value = true;
  try {
    await api.authors.toggleFollow(authorId);
    if (owner !== identityVersion) return;
    await loadFollows();
    if (owner === identityVersion) toast.show('关注状态已更新', 'ok');
  } catch (e) {
    if (owner === identityVersion)
      toast.show((e as Error).message || '操作失败', 'error');
  } finally {
    if (owner === identityVersion) followsBusy.value = false;
  }
}

// --- skills ---
async function loadMySkills() {
  const owner = identityVersion;
  skillsBusy.value = true;
  await loadSection('skills', async () => {
    const result = await api.skills.my();
    if (owner === identityVersion) mySkills.value = result;
  });
  if (owner === identityVersion) skillsBusy.value = false;
}

function openSkillPublish() {
  skillPublishSkillId.value = '';
  skillPublishVersion.value = '0.1.0';
  skillPublishNotes.value = '';
  skillPublishCategory.value = '';
  skillPublishTags.value = '';
  skillZipFile.value = null;
  skillPublishOpen.value = true;
  const owner = identityVersion;
  api.skills
    .categories()
    .then((c) => {
      if (owner === identityVersion) skillAvailableCategories.value = c;
    })
    .catch(() => {});
}

function closeSkillPublish() {
  if (!skillPublishSaving.value) skillPublishOpen.value = false;
}

function pickSkillZip() {
  skillZipInput.value?.click();
}

function onSkillZipChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file) return;
  if (!/\.zip$/i.test(file.name) || file.size > 10 * 1024 * 1024) {
    toast.show('请选择不超过 10 MiB 的 ZIP 文件', 'error');
    return;
  }
  skillZipFile.value = file;
}

async function publishSkill() {
  if (skillPublishSaving.value) return;
  const owner = identityVersion;
  if (!skillZipFile.value) {
    toast.show('请选择 zip 文件', 'error');
    return;
  }
  if (!skillPublishSkillId.value.trim()) {
    toast.show('请输入 Skill ID', 'error');
    return;
  }
  skillPublishSaving.value = true;
  try {
    const fd = new FormData();
    fd.append('file', skillZipFile.value);
    fd.append('skill_id', skillPublishSkillId.value.trim());
    fd.append('version', skillPublishVersion.value.trim() || '0.1.0');
    if (skillPublishNotes.value.trim())
      fd.append('release_notes', skillPublishNotes.value.trim());
    if (skillPublishCategory.value) {
      fd.append('categories', skillPublishCategory.value);
    }
    if (skillPublishTags.value.trim()) {
      fd.append('tags', skillPublishTags.value.trim());
    }
    await api.skills.create(fd);
    if (owner !== identityVersion) return;
    skillPublishOpen.value = false;
    toast.show('Skill 发布成功！', 'ok');
    await loadMySkills();
  } catch (e) {
    const msg = e instanceof Error ? e.message : '发布失败';
    if (owner === identityVersion) toast.show(msg, 'error');
  } finally {
    if (owner === identityVersion) skillPublishSaving.value = false;
  }
}

async function deleteSkill(skillId: string) {
  if (
    skillDeleteBusy.value ||
    !(await confirmAction(`确认删除 ${skillId} 吗？`))
  )
    return;
  const owner = identityVersion;
  skillDeleteBusy.value = true;
  try {
    await api.skills.delete(skillId);
    if (owner !== identityVersion) return;
    mySkills.value = mySkills.value.filter((s) => s.skill_id !== skillId);
    toast.show('Skill 已删除', 'ok');
  } catch (e) {
    if (owner === identityVersion)
      toast.show((e as Error).message || '删除失败', 'error');
  } finally {
    if (owner === identityVersion) skillDeleteBusy.value = false;
  }
}

async function loadWorkspace() {
  const owner = identityVersion;
  loading.value = true;
  await Promise.all([
    loadPlugins(),
    loadAccessToken(),
    loadSubscriptions(),
    loadFollows(),
    loadMySkills(),
    taxonomy.load().catch(() => {}),
  ]);
  if (owner === identityVersion) loading.value = false;
}
watch(
  () => auth.viewer?.author_id,
  (id) => {
    ++identityVersion;
    ++snapshotVersion;
    plugins.value = [];
    selectedId.value = null;
    snapshot.value = null;
    selectedPlugin.value = null;
    subscriptions.value = [];
    follows.value = [];
    mySkills.value = [];
    accessToken.value = null;
    accessTokenValue.value = '';
    metadataOpen.value = false;
    skillPublishOpen.value = false;
    sectionErrors.value = {};
    sectionLoading.value = {};
    snapshotLoading.value = false;
    metadataSaving.value = false;
    iconUploading.value = false;
    accessTokenBusy.value = false;
    subscriptionsBusy.value = false;
    followsBusy.value = false;
    skillsBusy.value = false;
    skillPublishSaving.value = false;
    pluginActionBusy.value = false;
    skillDeleteBusy.value = false;
    skillZipFile.value = null;
    metadataDisplayName.value = '';
    metadataIconUrl.value = '';
    metadataTags.value = '';
    skillPublishNotes.value = '';
    if (id) void loadWorkspace();
    else loading.value = false;
  },
  { immediate: true },
);
onMounted(async () => {
  await auth.loadViewer();
  authChecking.value = false;
});
let returnFocus: HTMLElement | null = null;
watch(
  () => metadataOpen.value || skillPublishOpen.value,
  async (open) => {
    if (open) {
      returnFocus = document.activeElement as HTMLElement;
      await nextTick();
      document
        .querySelector<HTMLElement>(
          '.me-modal input:not([type=file]), .me-modal button',
        )
        ?.focus();
    } else returnFocus?.focus();
  },
);
function trapDialog(event: KeyboardEvent) {
  if (event.key !== 'Tab') return;
  const dialog = (event.currentTarget as HTMLElement).querySelector(
    '.me-modal',
  );
  const controls = Array.from(
    dialog?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]):not([type=file]), select:not([disabled]), textarea:not([disabled]), a[href]',
    ) || [],
  );
  const first = controls[0],
    last = controls[controls.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last?.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first?.focus();
  }
}
onBeforeUnmount(() => {
  ++identityVersion;
  ++snapshotVersion;
  accessTokenValue.value = '';
});
</script>

<template>
  <div class="page-wrap me-page">
    <header class="dossier-heading">
      <div class="desk-running"><b>创作事务</b><span>个人版 · 案头</span></div>
      <div class="desk-headline">
        <h1>创作者工作台</h1>
        <p>维护作品、发布 Skill，整理你订阅的插件与关注的作者。</p>
      </div>
      <RouterLink v-if="auth.isAuthenticated" class="btn" to="/me/profile"
        >编辑个人档案 ↗</RouterLink
      >
    </header>
    <PageSkeleton v-if="authChecking || auth.loading" type="rows" :count="3" />
    <section v-else-if="auth.error" class="section-error" role="alert">
      <h2>暂时无法确认登录状态</h2>
      <p>{{ auth.error }}</p>
      <button class="btn" @click="auth.loadViewer(true)">重新连接</button>
    </section>
    <section v-else-if="!auth.isAuthenticated" class="access-panel">
      <div class="desk-entry">
        <span class="desk-label">账号入口</span>
        <h2>登录你的工作台</h2>
        <p>使用发布作品时的 GitHub 账号登录，即可查阅插件版本、更新公开资料与管理访问令牌。</p>
        <div class="desk-actions">
          <a class="btn btn-primary" :href="auth.getLoginUrl('/me')">使用 GitHub 登录 ↗</a>
          <RouterLink class="access-browse" to="/browse">浏览插件目录 →</RouterLink>
        </div>
      </div>
      <aside class="desk-index" aria-label="工作台栏目">
        <h3>案头索引</h3>
        <ol>
          <li><strong>插件与版本</strong><span>编辑资料，查看维护记录。</span></li>
          <li><strong>我的 Skills</strong><span>发布、更新和管理技能包。</span></li>
          <li><strong>订阅与关注</strong><span>查阅订阅的插件与关注的作者。</span></li>
          <li><strong>访问令牌</strong><span>为 Neo-MoFox 实例接入市场。</span></li>
        </ol>
      </aside>
    </section>
    <template v-else>
      <section v-if="auth.viewer" class="identity-strip">
        <div class="identity-avatar">
          <img
            v-if="auth.viewer.avatar_url"
            :src="auth.viewer.avatar_url"
            alt=""
          /><span v-else>{{ auth.viewer.display_name?.[0] || 'M' }}</span>
        </div>
        <div>
          <strong>{{ auth.viewer.display_name }}</strong
          ><small>@{{ auth.viewer.github_login }}</small>
        </div>
        <span class="identity-id">{{ auth.viewer.author_id }}</span
        ><button
          class="btn btn-ghost btn-sm"
          @click="copyText(auth.viewer.author_id, '用户 ID 已复制')"
        >
          复制 ID</button
        ><RouterLink
          class="btn btn-ghost btn-sm"
          :to="`/author/${encodeURIComponent(auth.viewer.author_id)}`"
          >公开主页 ↗</RouterLink
        >
      </section>
      <nav class="workspace-tabs" aria-label="工作台栏目">
        <button
          v-for="tab in workspaceTabs"
          :key="tab.key"
          type="button"
          :class="{ active: activeTab === tab.key }"
          :aria-pressed="activeTab === tab.key"
          @click="activeTab = tab.key"
        >
          {{ tab.label
          }}<span v-if="tab.key === 'plugins' && !loading && !sectionLoading.plugins && !sectionErrors.plugins">{{ plugins.length }}</span
          ><span v-if="tab.key === 'skills' && !loading && !skillsBusy && !sectionErrors.skills">{{ mySkills.length }}</span>
        </button>
      </nav>
      <PageSkeleton v-if="loading" type="rows" :count="4" />
      <div v-else class="workspace-content">
        <section
          class="me-token-card"
          v-show="activeTab === 'token'"
          data-anim="enter-2"
        >
          <div>
            <span class="kicker">实例接入</span>
            <h2>插件市场访问令牌</h2>
            <p>
              Neo-MoFox
              接入插件市场时使用这个单实例令牌。重新生成后，旧令牌会立即失效。
            </p>
          </div>
          <PageSkeleton v-if="sectionLoading.token" type="rows" :count="2" />
          <div
            v-else-if="sectionErrors.token"
            class="section-error"
            role="status"
          >
            <p>{{ sectionErrors.token }}</p>
            <button class="btn" @click="loadAccessToken">重试</button>
          </div>
          <div v-else class="me-token-meta">
            <div class="me-token-summary">
              <span
                class="badge"
                :class="
                  accessToken?.has_token
                    ? 'status-published'
                    : 'status-archived'
                "
              >
                {{ accessToken?.has_token ? '已启用' : '未生成' }}
              </span>
              <span
                v-if="accessToken?.token_preview"
                class="me-token-preview"
                >{{ accessToken.token_preview }}</span
              >
              <span v-if="accessToken?.last_used_at" class="me-token-used"
                >最近使用 {{ formatRelative(accessToken.last_used_at) }}</span
              >
            </div>
            <div class="me-token-actions">
              <button
                type="button"
                class="btn btn-sm"
                :disabled="accessTokenBusy"
                @click="rotateAccessToken"
              >
                {{ accessToken?.has_token ? '重新生成令牌' : '生成令牌' }}
              </button>
              <button
                type="button"
                class="btn btn-sm btn-ghost"
                :disabled="!accessToken?.has_token || accessTokenBusy"
                @click="revokeAccessToken"
              >
                撤销
              </button>
            </div>
          </div>
          <div v-if="accessTokenValue" class="me-token-secret">
            <span>新令牌</span>
            <code>{{ accessTokenValue }}</code>
            <button
              type="button"
              class="btn btn-sm"
              @click="copyText(accessTokenValue, '访问令牌已复制')"
            >
              复制令牌
            </button>
          </div>
        </section>

        <div
          v-show="activeTab === 'collection'"
          class="me-sub-follow-grid"
          data-anim="enter-3"
        >
          <section class="me-sub-card">
            <div class="me-section-head">
              <h2>我的订阅</h2>
              <small>{{ subscriptions.length }}</small>
            </div>
            <PageSkeleton
              v-if="sectionLoading.subscriptions"
              type="rows"
              :count="2"
            />
            <div
              v-else-if="sectionErrors.subscriptions"
              class="section-error"
              role="status"
            >
              <p>{{ sectionErrors.subscriptions }}</p>
              <button class="btn" @click="loadSubscriptions">重试</button>
            </div>
            <div v-else-if="subscriptions.length" class="me-sub-list">
              <div
                v-for="item in subscriptions"
                :key="item.plugin_id"
                class="me-sub-row"
              >
                <div class="me-sub-row-icon">
                  <img
                    v-if="item.icon_url"
                    :src="item.icon_url"
                    :alt="item.display_name"
                  />
                  <template v-else>{{
                    item.display_name[0]?.toUpperCase() || '?'
                  }}</template>
                </div>
                <div class="me-sub-row-info">
                  <div class="me-sub-row-head">
                    <router-link
                      :to="`/plugin/${encodeURIComponent(item.plugin_id)}`"
                      class="me-sub-row-name"
                      >{{ item.display_name }}</router-link
                    >
                    <span :class="['badge', `status-${item.status}`]">{{
                      statusText(item.status)
                    }}</span>
                  </div>
                  <small class="me-sub-row-meta"
                    >{{ item.plugin_id }} ·
                    {{
                      item.owner_display_name ||
                      item.owner_login ||
                      item.owner_id
                    }}
                    · 订阅于 {{ formatRelative(item.subscribed_at) }}</small
                  >
                </div>
                <button
                  type="button"
                  class="btn btn-sm btn-ghost"
                  :disabled="subscriptionsBusy"
                  @click="unsubscribe(item.plugin_id)"
                >
                  取消订阅
                </button>
              </div>
            </div>
            <EmptyState
              v-else
              title="暂无订阅"
              message="浏览插件市场，订阅感兴趣的项目后，这里会集中展示。"
            />
          </section>

          <section class="me-sub-card">
            <div class="me-section-head">
              <h2>我的关注</h2>
              <small>{{ follows.length }}</small>
            </div>
            <PageSkeleton
              v-if="sectionLoading.follows"
              type="rows"
              :count="2"
            />
            <div
              v-else-if="sectionErrors.follows"
              class="section-error"
              role="status"
            >
              <p>{{ sectionErrors.follows }}</p>
              <button class="btn" @click="loadFollows">重试</button>
            </div>
            <div v-else-if="follows.length" class="me-sub-list">
              <div
                v-for="item in follows"
                :key="item.author_id"
                class="me-sub-row"
              >
                <div class="me-sub-row-icon">
                  <img
                    v-if="item.avatar_url"
                    :src="item.avatar_url"
                    :alt="item.display_name"
                  />
                  <template v-else>{{
                    item.display_name[0]?.toUpperCase() || '?'
                  }}</template>
                </div>
                <div class="me-sub-row-info">
                  <div class="me-sub-row-head">
                    <router-link
                      :to="`/author/${encodeURIComponent(item.author_id)}`"
                      class="me-sub-row-name"
                      >{{ item.display_name }}</router-link
                    >
                  </div>
                  <small class="me-sub-row-meta"
                    >@{{ item.github_login }} · {{ item.author_id }} · 关注于
                    {{ formatRelative(item.followed_at) }}</small
                  >
                </div>
                <button
                  type="button"
                  class="btn btn-sm btn-ghost"
                  :disabled="followsBusy"
                  @click="unfollow(item.author_id)"
                >
                  取消关注
                </button>
              </div>
            </div>
            <EmptyState
              v-else
              title="暂无关注"
              message="关注作者后，这里会集中展示你关注的创作者。"
            />
          </section>
        </div>

        <!-- My Skills -->
        <section v-show="activeTab === 'skills'" class="me-card">
          <div class="me-section-head">
            <h2>我的 Skills</h2>
            <small>{{ mySkills.length }}</small>
          </div>
          <PageSkeleton v-if="sectionLoading.skills" type="rows" :count="2" />
          <div
            v-else-if="sectionErrors.skills"
            class="section-error"
            role="status"
          >
            <p>{{ sectionErrors.skills }}</p>
            <button class="btn" @click="loadMySkills">重试</button>
          </div>
          <div v-else-if="mySkills.length" class="me-sub-list">
            <div v-for="sk in mySkills" :key="sk.skill_id" class="me-sub-row">
              <div class="me-sub-row-icon">
                <img
                  v-if="sk.icon_url"
                  :src="sk.icon_url"
                  :alt="sk.display_name"
                />
                <template v-else>{{
                  sk.display_name[0]?.toUpperCase() || '?'
                }}</template>
              </div>
              <div class="me-sub-row-info">
                <div class="me-sub-row-head">
                  <router-link
                    :to="`/skill/${encodeURIComponent(sk.skill_id)}`"
                    class="me-sub-row-name"
                    >{{ sk.display_name }}</router-link
                  >
                  <span v-if="sk.latest_version" class="badge status-published"
                    >v{{ sk.latest_version }}</span
                  >
                </div>
                <small class="me-sub-row-meta"
                  >{{ sk.skill_id }} · ⬇ {{ sk.download_count }} · ⭐
                  {{ sk.rating_avg?.toFixed(1) || '-' }} ·
                  {{ formatRelative(sk.updated_at) }}</small
                >
              </div>
              <button
                type="button"
                class="btn btn-sm btn-ghost"
                :disabled="skillDeleteBusy"
                @click="deleteSkill(sk.skill_id)"
              >
                删除
              </button>
            </div>
          </div>
          <EmptyState
            v-else
            title="还没有 Skill"
            message="发布你的第一个 Skill 吧！"
          />
          <div style="margin-top: var(--space-3)">
            <button
              type="button"
              class="btn btn-primary btn-sm"
              @click="openSkillPublish"
            >
              发布新 Skill
            </button>
          </div>
        </section>

        <div
          v-show="activeTab === 'plugins'"
          class="me-layout"
          data-anim="enter-4"
        >
          <!-- Plugin list (left) -->
          <aside class="me-plugin-list">
            <div class="me-section-head">
              <h2>我的插件</h2>
              <small>{{ plugins.length }}</small>
            </div>
            <PageSkeleton
              v-if="sectionLoading.plugins"
              type="rows"
              :count="2"
            />
            <div
              v-else-if="sectionErrors.plugins"
              class="section-error"
              role="status"
            >
              <p>{{ sectionErrors.plugins }}</p>
              <button class="btn" @click="loadPlugins">重试</button>
            </div>
            <div v-else-if="plugins.length" class="me-plugin-rail">
              <button
                v-for="p in plugins"
                :key="p.plugin_id"
                type="button"
                :class="[
                  'me-plugin-item',
                  { 'is-active': p.plugin_id === selectedId },
                ]"
                @click="selectPlugin(p.plugin_id)"
              >
                <div class="me-plugin-item-icon">
                  <img
                    v-if="p.icon_url"
                    :src="p.icon_url"
                    :alt="p.display_name"
                  />
                  <template v-else>{{
                    p.display_name[0]?.toUpperCase() || '?'
                  }}</template>
                </div>
                <div class="me-plugin-item-info">
                  <strong>{{ p.display_name }}</strong>
                  <small>{{ p.plugin_id }}</small>
                  <div class="me-plugin-item-meta">
                    <span :class="['badge', `status-${p.status}`]">{{
                      statusText(p.status)
                    }}</span>
                    <span class="muted">{{
                      formatRelative(p.updated_at)
                    }}</span>
                  </div>
                </div>
              </button>
            </div>
            <EmptyState
              v-else
              title="还没有插件"
              message="使用 MPDT CLI 上传第一个插件后，这里会出现管理入口。"
            />
          </aside>

          <!-- Main detail -->
          <div class="me-main">
            <PageSkeleton v-if="snapshotLoading" type="detail" :count="3" />
            <div
              v-else-if="sectionErrors.snapshot"
              class="section-error"
              role="status"
            >
              <p>{{ sectionErrors.snapshot }}</p>
              <button class="btn" @click="loadSnapshot">重新加载资料</button>
            </div>

            <template v-else-if="selectedPlugin">
              <section class="me-card plugin-lead">
                <div class="me-section-head">
                  <div>
                    <span class="desk-label">当前插件</span><h2>{{ selectedPlugin.display_name }}</h2>
                    <p class="me-section-summary">
                      {{ selectedPlugin.summary }}
                    </p>
                  </div>
                  <div class="me-section-actions">
                    <button class="btn btn-sm" @click="openMetadataEditor">
                      编辑资料
                    </button>
                    <span
                      :class="['badge', `status-${selectedPlugin.status}`]"
                      >{{ statusText(selectedPlugin.status) }}</span
                    >
                    <TrustBadge :level="selectedPlugin.trust_level" />
                  </div>
                </div>
                <section class="me-metric-row">
                  <div class="me-metric">
                    <span>当前状态</span>
                    <strong>{{ statusText(selectedPlugin.status) }}</strong>
                    <small>{{ formatRelative(selectedPlugin.updated_at) }}</small>
                  </div>
                  <div class="me-metric">
                    <span>版本总数</span>
                    <strong>{{ snapshot?.versions?.length || 0 }}</strong>
                    <small
                      >{{
                        (snapshot?.versions || []).filter((v) => v.is_yanked)
                          .length
                      }}
                      个已下架</small
                    >
                  </div>
                  <div class="me-metric">
                    <span>社区</span>
                    <strong
                      >{{ formatNumber(selectedPlugin.comments_count) }} /
                      {{ formatNumber(selectedPlugin.rating_count) }}</strong
                    >
                    <small>评论 / 评分</small>
                  </div>
                  <div class="me-metric">
                    <span>热度</span>
                    <strong
                      >{{ formatNumber(selectedPlugin.likes_count) }} 订阅</strong
                    >
                    <small
                      >{{
                        formatNumber(selectedPlugin.downloads_count)
                      }}
                      下载</small
                    >
                  </div>
                </section>
                <div class="me-info-grid">
                  <div>
                    <h4>基础信息</h4>
                    <ul class="me-meta-list">
                      <li>
                        <span>插件 ID</span
                        ><strong>{{ selectedPlugin.plugin_id }}</strong>
                      </li>
                      <li>
                        <span>最新版本</span
                        ><strong>{{
                          selectedPlugin.latest_version || '-'
                        }}</strong>
                      </li>
                      <li>
                        <span>分类标签</span>
                        <strong>{{
                          [
                            ...(selectedPlugin.categories || []).map(
                              categoryLabel,
                            ),
                            ...(selectedPlugin.tags || []),
                          ].join(' / ') || '未设置'
                        }}</strong>
                      </li>
                      <li>
                        <span>仓库</span>
                        <strong
                          ><a
                            :href="selectedPlugin.repository_url"
                            target="_blank"
                            rel="noreferrer noopener"
                            >查看源码 →</a
                          ></strong
                        >
                      </li>
                    </ul>
                  </div>
                  <div>
                    <h4>危险操作</h4>
                    <p class="me-soft-note">
                      删除会移除插件、版本、评论与审核记录。建议只在确认废弃整个项目时使用。
                    </p>
                    <button
                      class="btn btn-danger"
                      :disabled="pluginActionBusy"
                      @click="deletePlugin(selectedPlugin.plugin_id)"
                    >
                      删除插件
                    </button>
                  </div>
                </div>
              </section>

              <section class="me-card">
                <div class="me-section-head">
                  <h2>版本管理</h2>
                  <small v-if="snapshot?.versions?.length"
                    >{{ snapshot.versions.length }} 个版本</small
                  >
                </div>
                <div
                  v-if="(snapshot?.versions || []).length"
                  class="me-version-list"
                >
                  <div
                    v-for="v in snapshot!.versions"
                    :key="v.version"
                    class="me-version-row"
                  >
                    <div class="me-version-main">
                      <div class="me-version-head">
                        <strong>v{{ v.version }}</strong>
                        <span :class="['badge', `status-${v.status}`]">{{
                          statusText(v.status)
                        }}</span>
                        <span v-if="v.is_yanked" class="badge status-blocked"
                          >已 yank</span
                        >
                      </div>
                      <p>{{ v.release_title || v.version }}</p>
                      <small
                        >{{ formatDate(v.published_at) }} ·
                        {{ formatBytes(v.file_size) }} ·
                        {{ formatNumber(v.download_count) }} 下载 · API
                        {{ v.plugin_api_version }} · Host >=
                        {{ v.min_host_version
                        }}{{
                          v.max_host_version ? ` <= ${v.max_host_version}` : ''
                        }}</small
                      >
                    </div>
                    <div class="me-version-actions">
                      <a
                        class="btn btn-xs btn-ghost"
                        :href="v.release_url"
                        target="_blank"
                        rel="noreferrer noopener"
                        >Release</a
                      >
                      <button
                        v-if="!v.is_yanked"
                        class="btn btn-xs"
                        :disabled="pluginActionBusy"
                        @click="
                          yankVersion(selectedPlugin.plugin_id, v.version)
                        "
                      >
                        下架
                      </button>
                    </div>
                  </div>
                </div>
                <EmptyState
                  v-else
                  title="暂无版本"
                  message="当前插件还没有任何可管理的版本。"
                />
              </section>

              <section class="me-card">
                <div class="me-section-head">
                  <h2>最近治理记录</h2>
                </div>
                <div
                  v-if="(snapshot?.recent_reviews || []).length"
                  class="me-review-feed"
                >
                  <article
                    v-for="item in snapshot!.recent_reviews"
                    :key="item.id || item.created_at"
                    class="me-review-item"
                  >
                    <div>
                      <strong>{{ reviewActionText(item.action) }}</strong>
                      <p>
                        {{ item.target_id }} · {{ item.status_before || '-' }} →
                        {{ item.status_after || '-' }}
                      </p>
                    </div>
                    <div class="me-review-meta">
                      <span>{{ item.operator_id }}</span>
                      <span>{{ formatRelative(item.created_at) }}</span>
                    </div>
                  </article>
                </div>
                <EmptyState
                  v-else
                  title="暂无记录"
                  message="这个插件还没有任何治理记录。"
                />
              </section>
            </template>
            <section v-else-if="!sectionErrors.plugins" class="me-card desk-blank">
              <span class="desk-label">作品专栏</span>
              <h2>{{ plugins.length ? '选择一份插件档案' : '第一份插件，从这里接入' }}</h2>
              <p>{{ plugins.length ? '在作品索引中选择插件，即可编辑资料并查看版本记录。' : '用 MPDT CLI 上传插件后，作品资料和版本就会归入这个工作台。' }}</p>
              <button v-if="!plugins.length" class="btn" @click="activeTab = 'token'">查看访问令牌 →</button>
            </section>
          </div>
        </div>
      </div>
      <!-- Metadata editor modal -->
      <div
        v-if="metadataOpen"
        class="me-modal-backdrop"
        @keydown="trapDialog"
        @click.self="closeMetadataEditor"
        @keydown.esc="closeMetadataEditor"
      >
        <section
          class="me-modal"
          role="dialog"
          aria-modal="true"
          aria-label="编辑或发布内容"
          tabindex="-1"
        >
          <header class="me-modal-head">
            <div>
              <span class="kicker">EDIT METADATA</span>
              <h2>编辑插件资料</h2>
            </div>
            <button
              type="button"
              class="btn btn-ghost btn-sm"
              @click="closeMetadataEditor"
            >
              关闭
            </button>
          </header>
          <div class="me-modal-body">
            <label class="me-form-field">
              <span>显示名</span>
              <input v-model="metadataDisplayName" type="text" maxlength="80" />
            </label>
            <label class="me-form-field">
              <span>图标</span>
              <div class="me-form-icon-row">
                <input
                  v-model="metadataIconUrl"
                  type="url"
                  placeholder="https://... 或上传后自动填入"
                />
                <button
                  type="button"
                  class="btn btn-sm"
                  :disabled="iconUploading || metadataSaving"
                  @click="pickIcon"
                >
                  {{ iconUploading ? '上传中…' : '上传图标' }}
                </button>
                <input
                  ref="iconFileInput"
                  class="me-form-file"
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/gif"
                  @change="onIconFileChange"
                />
              </div>
              <small class="me-form-hint"
                >支持 PNG / JPEG / WEBP / GIF，最大 2 MiB，会归一化为 512×512
                PNG。</small
              >
            </label>
            <label class="me-form-field">
              <span>分类</span>
              <MarketSelect v-model="metadataCategory">
                <option value="">未设置</option>
                <option
                  v-for="item in EDITABLE_PLUGIN_CATEGORIES"
                  :key="item"
                  :value="item"
                >
                  {{ categoryLabel(item) }}
                </option>
              </MarketSelect>
              <small class="me-form-hint"
                >当前仅支持选择一个分类：聊天互动、休闲娱乐、信息资讯、社区管理、实用工具。</small
              >
            </label>
            <label class="me-form-field">
              <span>标签（用逗号分隔）</span>
              <input
                v-model="metadataTags"
                type="text"
                placeholder="例如 chat, group, fun"
              />
            </label>
          </div>
          <footer class="me-modal-foot">
            <button
              type="button"
              class="btn btn-ghost"
              :disabled="metadataSaving || iconUploading"
              @click="closeMetadataEditor"
            >
              取消
            </button>
            <button
              type="button"
              class="btn btn-primary"
              :disabled="metadataSaving || iconUploading"
              @click="saveMetadataPatch"
            >
              {{ metadataSaving ? '保存中…' : '保存' }}
            </button>
          </footer>
        </section>
      </div>

      <!-- Skill publish modal -->
      <div
        v-if="skillPublishOpen"
        class="me-modal-backdrop"
        @keydown="trapDialog"
        @click.self="closeSkillPublish"
        @keydown.esc="closeSkillPublish"
      >
        <section
          class="me-modal"
          role="dialog"
          aria-modal="true"
          aria-label="编辑或发布内容"
          tabindex="-1"
        >
          <header class="me-modal-head">
            <div>
              <span class="kicker">PUBLISH SKILL</span>
              <h2>发布新 Skill</h2>
            </div>
            <button
              type="button"
              class="btn btn-ghost btn-sm"
              @click="closeSkillPublish"
            >
              关闭
            </button>
          </header>
          <div class="me-modal-body">
            <label class="me-form-field">
              <span>Skill ID</span>
              <input
                v-model="skillPublishSkillId"
                type="text"
                placeholder="例如 arxiv-watcher"
                maxlength="120"
              />
            </label>
            <label class="me-form-field">
              <span>版本号</span>
              <input
                v-model="skillPublishVersion"
                type="text"
                placeholder="0.1.0"
              />
            </label>
            <label class="me-form-field">
              <span>更新说明（可选）</span>
              <input
                v-model="skillPublishNotes"
                type="text"
                placeholder="初始版本"
              />
            </label>
            <label class="me-form-field">
              <span>分类</span>
              <MarketSelect v-model="skillPublishCategory">
                <option value="">未选择</option>
                <option
                  v-for="cat in skillAvailableCategories"
                  :key="cat"
                  :value="cat"
                >
                  {{ cat }}
                </option>
              </MarketSelect>
              <small
                v-if="!skillAvailableCategories.length"
                class="me-form-hint"
                >暂无可用分类</small
              >
            </label>
            <label class="me-form-field">
              <span>标签（用逗号分隔）</span>
              <input
                v-model="skillPublishTags"
                type="text"
                placeholder="ai, paper"
              />
            </label>
            <label class="me-form-field">
              <span>Skill Zip 包</span>
              <div class="me-form-icon-row">
                <input
                  type="text"
                  readonly
                  :value="skillZipFile?.name || '未选择文件'"
                  placeholder="选择 zip 文件…"
                />
                <button type="button" class="btn btn-sm" @click="pickSkillZip">
                  选择文件
                </button>
                <input
                  ref="skillZipInput"
                  class="me-form-file"
                  type="file"
                  accept=".zip"
                  @change="onSkillZipChange"
                />
              </div>
              <small class="me-form-hint"
                >上传包含 SKILL.md 的 zip 包，最大 10 MiB。</small
              >
            </label>
          </div>
          <footer class="me-modal-foot">
            <button
              type="button"
              class="btn btn-ghost"
              :disabled="skillPublishSaving"
              @click="closeSkillPublish"
            >
              取消
            </button>
            <button
              type="button"
              class="btn btn-primary"
              :disabled="skillPublishSaving || !skillZipFile"
              @click="publishSkill"
            >
              {{ skillPublishSaving ? '发布中…' : '发布' }}
            </button>
          </footer>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.me-page {
  display: grid;
  gap: 24px;
}
.dossier-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 18px;
  padding-bottom: 26px;
  border-bottom: 3px double var(--ink-700);
}
.desk-running {
  grid-column: 1 / -1;
  display: flex;
  justify-content: space-between;
  border-top: 2px solid var(--ink-900);
  border-bottom: 1px solid var(--line-strong);
  padding: 8px 0;
  font-size: 11px;
  letter-spacing: .1em;
}
.desk-running b, .desk-label, .kicker { color: var(--blue-700); }
.desk-running span, .desk-label, .kicker { font: 11px/1.5 var(--font-mono); }
.dossier-heading h1 {
  margin: 4px 0 14px;
  font: 800 clamp(40px, 5.5vw, 76px)/1.16 var(--font-editorial);
  letter-spacing: -.045em;
}
.dossier-heading p { margin: 0; color: var(--ink-700); line-height: 1.8; }
.access-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(220px, 1fr);
  gap: clamp(24px, 5vw, 72px);
  padding-block: 16px 30px;
  border-bottom: 1px solid var(--line-strong);
}
.desk-entry { align-self: center; padding: clamp(12px, 3vw, 38px) 0; }
.desk-label { display: block; letter-spacing: .12em; }
.desk-entry h2, .desk-blank h2 {
  margin: 13px 0;
  font: 800 clamp(25px, 3vw, 41px)/1.3 var(--font-editorial);
}
.desk-entry p, .desk-blank p { margin: 0; max-width: 36em; color: var(--ink-700); line-height: 1.85; }
.desk-actions { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; margin-top: 24px; }
.access-browse { color: var(--blue-700); font-size: 13px; }
.desk-index { border-left: 1px solid var(--line-strong); padding-left: clamp(20px, 3vw, 40px); }
.desk-index h3 { font: 800 19px var(--font-editorial); margin: 0 0 13px; }
.desk-index ol { list-style: decimal-leading-zero; padding: 0 0 0 2em; margin: 0; }
.desk-index li { padding: 8px 0 9px 6px; border-top: 1px solid var(--line); }
.desk-index li::marker { color: var(--blue-700); font: 11px var(--font-mono); }
.desk-index li strong, .desk-index li span { display: block; }
.desk-index li strong { font-size: 13px; }
.desk-index li span { margin-top: 3px; color: var(--ink-500); font-size: 12px; line-height: 1.5; }
.desk-blank { border-top: 2px solid var(--ink-700); }
.desk-blank .btn { margin-top: 18px; }
.identity-strip {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 0 16px;
  border-bottom: 1px solid var(--line);
}
.identity-avatar {
  width: 44px;
  height: 44px;
  background: var(--blue-100);
  color: var(--blue-700);
  display: grid;
  place-items: center;
  border-radius: 4px;
  overflow: hidden;
  flex-shrink: 0;
}
.identity-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.identity-strip > div:nth-child(2) {
  display: grid;
  gap: 3px;
}
.identity-strip small {
  font-size: 11px;
  color: var(--ink-500);
}
.identity-id {
  margin-left: auto;
  font: 11px var(--font-mono);
  color: var(--ink-500);
  overflow-wrap: anywhere;
}
.workspace-tabs {
  display: flex;
  border-bottom: 1px solid var(--line);
  gap: 24px;
  overflow: auto;
}
.workspace-tabs button {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
  padding: 12px 0;
  border-bottom: 2px solid transparent;
  color: var(--ink-500);
  font: 700 15px/1.5 var(--font-editorial);
}
.workspace-tabs button.active {
  border-color: var(--blue-500);
  color: var(--blue-600);
  font-weight: 700;
}
.workspace-tabs button span {
  background: var(--surface-soft);
  padding: 1px 6px;
  font: 11px var(--font-mono);
}
.me-layout {
  display: grid;
  grid-template-columns: 250px minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}
.me-plugin-list,
.me-card,
.me-token-card,
.me-sub-card {
  border: 1px solid var(--line);
  background: var(--surface);
  padding: 22px;
  min-width: 0;
  border-radius: 0;
}
.me-main {
  display: grid;
  gap: 20px;
  min-width: 0;
}
.me-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 20px;
}
.me-section-head h2,
.me-token-card h2 {
  font: 800 22px/1.3 var(--font-editorial);
  margin: 0;
}
.plugin-lead { border-top: 2px solid var(--ink-700); }
.plugin-lead .me-section-head h2 { margin: 8px 0; font-size: clamp(26px, 3.3vw, 44px); overflow-wrap: anywhere; }
.plugin-lead .me-metric-row { margin-bottom: 22px; }
.me-page :deep(.empty-state) { border: 0; border-block: 1px solid var(--line); border-radius: 0; justify-items: start; text-align: left; padding: 20px 0; }
.me-page :deep(.empty-state svg) { display: none; }
.me-page :deep(.empty-state strong) { font: 800 18px/1.5 var(--font-editorial); }
.me-section-head small {
  color: var(--ink-500);
  font: 12px var(--font-mono);
}
.me-section-summary,
.me-soft-note {
  font-size: 13px;
  color: var(--ink-500);
  line-height: 1.75;
}
.me-section-summary {
  margin: 8px 0 0;
}
.me-section-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.me-plugin-rail {
  display: grid;
  gap: 6px;
}
.me-plugin-item {
  display: flex;
  gap: 12px;
  padding: 12px 10px;
  min-width: 0;
  text-align: left;
  border: 1px solid transparent;
}
.me-plugin-item:hover {
  background: var(--surface-soft);
}
.me-plugin-item.is-active {
  background: var(--blue-50);
  border-color: var(--blue-200);
  border-left: 3px solid var(--blue-500);
}
.me-plugin-item-icon,
.me-sub-row-icon {
  width: 36px;
  height: 36px;
  background: var(--surface-soft);
  color: var(--blue-600);
  display: grid;
  place-items: center;
  border-radius: 4px;
  flex-shrink: 0;
  overflow: hidden;
}
.me-plugin-item-icon img,
.me-sub-row-icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.me-plugin-item-info {
  display: grid;
  gap: 5px;
  min-width: 0;
}
.me-plugin-item-info strong {
  font-size: 13px;
}
.me-plugin-item-info small {
  font: 10px var(--font-mono);
  color: var(--ink-500);
  overflow-wrap: anywhere;
}
.me-plugin-item-meta {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
  font-size: 10px;
}
.me-metric-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border: 1px solid var(--line);
  background: var(--surface);
}
.me-metric {
  padding: 18px;
  border-right: 1px solid var(--line);
  display: grid;
  gap: 7px;
}
.me-metric:last-child {
  border: 0;
}
.me-metric span,
.me-metric small {
  font-size: 11px;
  color: var(--ink-500);
}
.me-metric strong {
  font-size: 19px;
  overflow-wrap: anywhere;
}
.me-info-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 26px;
}
.me-info-grid h4 {
  font-size: 13px;
  margin: 0 0 14px;
}
.me-info-grid > div:last-child {
  border-left: 1px solid var(--line);
  padding-left: 24px;
}
.me-meta-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 13px;
}
.me-meta-list li {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  font-size: 12px;
}
.me-meta-list li span {
  color: var(--ink-500);
  white-space: nowrap;
}
.me-meta-list strong {
  text-align: right;
  overflow-wrap: anywhere;
  font-weight: 500;
}
.me-version-list,
.me-review-feed,
.me-sub-list {
  display: grid;
}
.me-version-row,
.me-review-item,
.me-sub-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 18px 0;
  border-bottom: 1px solid var(--line-soft);
}
.me-version-row:last-child,
.me-review-item:last-child,
.me-sub-row:last-child {
  border-bottom: 0;
}
.me-version-head,
.me-version-actions,
.me-sub-row-head {
  display: flex;
  gap: 9px;
  flex-wrap: wrap;
  align-items: center;
}
.me-version-main {
  min-width: 0;
}
.me-version-main p {
  margin: 8px 0;
  font-size: 13px;
}
.me-version-main small,
.me-review-item p,
.me-review-meta,
.me-sub-row-meta {
  color: var(--ink-500);
  font-size: 11px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}
.me-review-item strong {
  font-size: 13px;
}
.me-review-meta {
  display: grid;
  text-align: right;
}
.me-sub-follow-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
.me-sub-row {
  align-items: flex-start;
}
.me-sub-row-info {
  flex: 1;
  min-width: 0;
}
.me-sub-row-name {
  font-weight: 600;
  font-size: 14px;
}
.me-sub-row-meta {
  display: block;
  margin-top: 7px;
}
.me-sub-row > button {
  flex-shrink: 0;
}
.me-token-card {
  display: grid;
  gap: 24px;
  max-width: 840px;
}
.me-token-card h2 {
  margin: 10px 0;
}
.me-token-card p {
  color: var(--ink-500);
  font-size: 13px;
  line-height: 1.7;
}
.me-token-meta,
.me-token-summary,
.me-token-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.me-token-meta {
  justify-content: space-between;
  border-top: 1px solid var(--line);
  padding-top: 20px;
}
.me-token-preview,
.me-token-used {
  font-size: 12px;
  color: var(--ink-500);
}
.me-token-secret {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 16px;
  background: var(--blue-50);
  border: 1px solid var(--blue-200);
}
.me-token-secret code {
  overflow-wrap: anywhere;
}
.section-error {
  padding: 20px;
  background: var(--danger-soft);
  color: var(--danger-ink);
  font-size: 13px;
}
.section-error p {
  margin: 0 0 14px;
  overflow-wrap: anywhere;
}
.me-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: var(--overlay-strong);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.me-modal {
  width: min(560px, 100%);
  max-height: 90dvh;
  overflow: auto;
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: 4px;
  box-shadow: var(--shadow-3);
}
.me-modal-head,
.me-modal-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
}
.me-modal-head {
  border-bottom: 1px solid var(--line);
}
.me-modal-head h2 {
  margin: 8px 0 0;
  font-size: 20px;
}
.me-modal-foot {
  justify-content: flex-end;
  border-top: 1px solid var(--line);
}
.me-modal-body {
  padding: 24px;
  display: grid;
  gap: 20px;
}
.me-form-field {
  display: grid;
  gap: 8px;
  font-size: 13px;
}
.me-form-field input:not([type='file']),
.me-form-field select {
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 10px 12px;
  background: var(--paper);
  width: 100%;
  min-width: 0;
}
.me-form-icon-row {
  display: flex;
  gap: 8px;
}
.me-form-icon-row .btn {
  white-space: nowrap;
}
.me-form-file {
  display: none;
}
.me-form-hint {
  font-size: 11px;
  color: var(--ink-500);
  line-height: 1.6;
}
@media (max-width: 1100px) {
  .me-layout {
    grid-template-columns: 210px minmax(0, 1fr);
  }
  .me-metric-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .me-metric {
    border-bottom: 1px solid var(--line);
  }
  .me-sub-follow-grid {
    grid-template-columns: 1fr;
  }
  .identity-id {
    display: none;
  }
  .identity-strip > div:nth-child(2) {
    margin-right: auto;
  }
}
@media (max-width: 760px) {
  .dossier-heading {
    grid-template-columns: 1fr;
    justify-items: start;
  }
  .desk-running { width: 100%; }
  .access-panel { grid-template-columns: 1fr; }
  .desk-index { border-left: 0; border-top: 1px solid var(--line); padding: 18px 0 0; }
  .identity-strip {
    flex-wrap: wrap;
  }
  .me-layout {
    grid-template-columns: 1fr;
  }
  .me-plugin-rail {
    display: flex;
    overflow: auto;
  }
  .me-plugin-item {
    min-width: 200px;
  }
  .me-info-grid {
    grid-template-columns: 1fr;
  }
  .me-info-grid > div:last-child {
    border-left: 0;
    padding-left: 0;
    border-top: 1px solid var(--line);
    padding-top: 20px;
  }
  .me-card,
  .me-plugin-list,
  .me-token-card,
  .me-sub-card {
    padding: 18px;
  }
  .me-section-head {
    flex-wrap: wrap;
  }
  .me-token-secret {
    grid-template-columns: 1fr;
  }
  .me-sub-row {
    flex-wrap: wrap;
  }
  .me-version-row {
    align-items: flex-start;
    flex-direction: column;
  }
  .workspace-tabs {
    gap: 22px;
  }
  .me-form-field input,
  .me-form-field select {
    font-size: 16px;
  }
  .me-modal-backdrop {
    padding: 12px;
  }
  .me-modal-body {
    padding: 18px;
  }
  .access-panel {
    padding: 0 0 24px;
  }
}
</style>
