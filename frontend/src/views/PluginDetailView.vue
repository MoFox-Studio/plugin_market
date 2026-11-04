<script setup lang="ts">
import { useMarketDialog } from '@/composables/useMarketDialog';
const { confirm: confirmAction, prompt: promptAction } = useMarketDialog();
import { computed, ref, watch, onBeforeUnmount } from 'vue';
import { useRoute } from 'vue-router';
import api from '@/api';
import { useAuthStore } from '@/stores/auth';
import { useSubscriptionStore } from '@/stores/subscriptions';
import { useToastStore } from '@/stores/toast';
import {
  formatNumber,
  formatRelative,
  formatDate,
  formatBytes,
  categoryLabel,
  statusText,
  trustLevelLabel,
} from '@/utils/format';
import type {
  Plugin,
  RatingInfo,
  PluginVersion,
  Dependency,
  Comment,
} from '@/types';
import MentionInput from '@/components/MentionInput.vue';
import RiskWarning from '@/components/RiskWarning.vue';
import RecommendationSection from '@/components/RecommendationSection.vue';
import CatalogFrame from '@/components/catalog/CatalogFrame.vue';
import DossierNavigation from '@/components/catalog/DossierNavigation.vue';
import DossierLead from '@/components/catalog/DossierLead.vue';
import ReadmeDocument from '@/components/catalog/ReadmeDocument.vue';
import { dossierChapter } from '@/components/catalog/dossierChapter';
import AppIcon from '@/components/AppIcon.vue';
import CatalogState from '@/components/catalog/CatalogState.vue';
import CatalogComment from '@/components/catalog/CatalogComment.vue';
import { useCatalogResource } from '@/components/catalog/useCatalogResource';
const props = defineProps<{ id: string }>();
const route = useRoute(),
  auth = useAuthStore(),
  subscriptions = useSubscriptionStore(),
  toast = useToastStore();
const pluginId = computed(() => props.id || String(route.params.id));
const main = useCatalogResource<{ plugin: Plugin; rating: RatingInfo } | null>(
  () => null,
);
const plugin = computed(() => main.data?.plugin),
  rating = computed(() => main.data?.rating);
const versions = useCatalogResource<PluginVersion[]>(() => []),
  dependencies = useCatalogResource<Dependency[]>(() => []),
  comments = useCatalogResource<Comment[]>(() => []);
const readme = useCatalogResource<{ exists?: boolean; html?: string }>(
  () => ({}),
);
const documentHtml = computed(() => {
  const html = readme.data.html?.trim();
  if (!readme.data.exists || !html) return '';
  const fragment = document.createElement('template');
  fragment.innerHTML = html;
  const hasContent = fragment.content.textContent?.trim() || fragment.content.querySelector('img[src],audio[src],video[src]');
  return hasContent ? html : '';
});
const authorDescription = computed(() => plugin.value?.description?.trim() || plugin.value?.summary?.trim() || '');
const projectLinks = computed(() => [
  { label: '项目仓库', href: plugin.value?.repository_url, icon: 'github' },
  { label: '项目主页', href: plugin.value?.homepage, icon: 'arrow' },
].filter((link) => link.href && /^https?:\/\//i.test(link.href)));
const guideLabel = computed(() => {
  if (readme.loading) return '使用说明';
  if (documentHtml.value) return '使用文档';
  return authorDescription.value ? '功能说明' : '项目资料';
});
function sectionLink(hash: '#usage' | '#get') {
  return { path: route.path, query: route.query, hash };
}
function pluginChapter(hash: string) {
  return hash === '#get' ? 'overview' : dossierChapter(hash);
}
const requestedVersion = computed(() =>
  typeof route.query.version === 'string' ? route.query.version : '',
);
const selectedVersion = computed(
  () =>
    versions.data.find(
      (item) =>
        !item.is_yanked &&
        item.status === 'published' &&
        (requestedVersion.value
          ? item.version === requestedVersion.value
          : !item.is_prerelease),
    )?.version || '',
);
const latestVersion = computed(() =>
  versions.data.find((item) => item.version === selectedVersion.value),
);
const activeTab = ref('overview'),
  commentContent = ref(''),
  mentionIds = ref<string[]>([]),
  submitting = ref(false),
  subscriptionBusy = ref(false),
  ratingBusy = ref(false),
  installBusy = ref(false),
  deleting = ref<string | null>(null);
const expanded = ref<Record<string, boolean>>({});
let epoch = 0;
const subscribed = computed(
  () => subscriptions.get(pluginId.value) ?? plugin.value?.viewer_has_liked,
);
const ratingRows = computed(() => {
  const total = Object.values(rating.value?.distribution || {}).reduce(
    (sum, count) => sum + Number(count),
    0,
  );
  return [5, 4, 3, 2, 1].map((score) => {
    const count = Number(rating.value?.distribution?.[String(score)] || 0);
    return {
      score,
      count,
      percent: total ? Math.min(100, (count / total) * 100) : 0,
    };
  });
});
const threads = computed(() => {
  const byId = new Map(comments.data.map((item) => [String(item.id), item])),
    grouped = new Map<string, Comment[]>();
  for (const item of comments.data) {
    let root = item,
      visited = new Set<string>([String(item.id)]);
    while (
      root.parent_id != null &&
      byId.has(String(root.parent_id)) &&
      !visited.has(String(root.parent_id))
    ) {
      visited.add(String(root.parent_id));
      root = byId.get(String(root.parent_id))!;
    }
    const key = String(root.id);
    if (!grouped.has(key)) grouped.set(key, []);
    if (String(item.id) !== key) grouped.get(key)!.push(item);
  }
  return [...grouped].map(([key, replies]) => ({
    root: byId.get(key)!,
    replies: replies.sort(
      (a, b) =>
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    ),
  }));
});
const path = () => `/api/v1/plugins/${encodeURIComponent(pluginId.value)}`;
function loadVersions() {
  const p = path();
  return versions.load(() =>
    api
      .get<{ items: PluginVersion[] }>(`${p}/versions`)
      .then((res) => res.items || []),
  );
}
function loadReadme() {
  const p = path();
  return readme.load(() => api.get(`${p}/readme`));
}
function loadDependencies() {
  const p = path();
  return dependencies.load(() =>
    api
      .get<{ items: Dependency[] }>(`${p}/dependencies`)
      .then((res) => res.items || []),
  );
}
async function loadComments() {
  const p = path(),
    current = epoch;
  await comments.load(() =>
    api
      .get<{ items: Comment[] }>(`${p}/comments?limit=50`)
      .then((res) => res.items || []),
  );
  if (current === epoch) revealChapter();
}
function loadData() {
  const p = path();
  void main.load(() => api.get(`${p}/community`));
  void loadVersions();
  void loadReadme();
  void loadDependencies();
  void loadComments();
}
async function refreshCommunity(current: number, id: string) {
  const result = await api.get<{ plugin: Plugin; rating: RatingInfo }>(
    `/api/v1/plugins/${encodeURIComponent(id)}/community`,
  );
  if (current === epoch) main.data = result;
}
function requireLogin() {
  if (auth.isAuthenticated) return false;
  toast.show('登录后即可参与社区互动', 'error');
  return true;
}
async function subscribe() {
  if (subscriptionBusy.value || requireLogin()) return;
  const id = pluginId.value,
    current = epoch;
  subscriptionBusy.value = true;
  try {
    const result = await api.plugins.toggleSubscription(id);
    if (current !== epoch) return;
    subscriptions.set(id, result.subscribed);
    if (main.data)
      main.data = {
        ...main.data,
        plugin: {
          ...main.data.plugin,
          viewer_has_liked: result.subscribed,
          likes_count: result.subscriptions_count,
        },
      };
    toast.show(result.subscribed ? '已订阅插件更新' : '已取消订阅', 'ok');
  } catch (e) {
    if (current === epoch) toast.show((e as Error).message, 'error');
  } finally {
    if (current === epoch) subscriptionBusy.value = false;
  }
}
async function rate(score: number | null) {
  if (ratingBusy.value || requireLogin()) return;
  const id = pluginId.value,
    current = epoch;
  ratingBusy.value = true;
  try {
    const p = `/api/v1/plugins/${encodeURIComponent(id)}/rating`;
    if (score === null) await api.del(p);
    else await api.post(p, { score });
    await refreshCommunity(current, id);
    if (current === epoch)
      toast.show(score === null ? '已清除评分' : '感谢你的评分', 'ok');
  } catch (e) {
    if (current === epoch) toast.show((e as Error).message, 'error');
  } finally {
    if (current === epoch) ratingBusy.value = false;
  }
}
async function submitComment() {
  const content = commentContent.value.trim();
  if (!content || submitting.value || requireLogin()) return;
  const p = path(),
    current = epoch;
  submitting.value = true;
  try {
    await api.post(`${p}/comments`, { content });
    if (current !== epoch) return;
    commentContent.value = '';
    mentionIds.value = [];
    if (main.data)
      main.data = {
        ...main.data,
        plugin: {
          ...main.data.plugin,
          comments_count: main.data.plugin.comments_count + 1,
        },
      };
    toast.show('评论已发布', 'ok');
    await loadComments();
  } catch (e) {
    if (current === epoch) toast.show((e as Error).message, 'error');
  } finally {
    if (current === epoch) submitting.value = false;
  }
}
async function removeComment(id: string) {
  if (deleting.value || !(await confirmAction('确定删除这条评论吗？'))) return;
  const p = path(),
    current = epoch;
  deleting.value = id;
  try {
    await api.del(`${p}/comments/${encodeURIComponent(id)}`);
    if (current !== epoch) return;
    toast.show('评论已删除', 'ok');
    await loadComments();
    await refreshCommunity(current, pluginId.value);
  } catch (e) {
    if (current === epoch) toast.show((e as Error).message, 'error');
  } finally {
    if (current === epoch) deleting.value = null;
  }
}
function canRemove(comment: Comment) {
  return (
    !!auth.viewer &&
    (auth.viewer.author_id === comment.author.author_id || auth.isAdmin)
  );
}
async function install() {
  if (installBusy.value || !selectedVersion.value) return;
  const p = path(),
    current = epoch;
  const tab = window.open('about:blank', '_blank');
  if (tab) tab.opener = null;
  installBusy.value = true;
  try {
    const result = await api.post<{ asset_download_url?: string }>(
      `${p}/install-record?version=${encodeURIComponent(selectedVersion.value)}`,
    );
    if (!result?.asset_download_url)
      throw new Error('暂时没有可获取的安装包。');
    const url = new URL(result.asset_download_url, location.origin);
    if (!['https:', 'http:'].includes(url.protocol))
      throw new Error('下载地址不可用。');
    if (tab) tab.location.href = url.href;
    else window.location.assign(url.href);
    if (current === epoch) {
      if (main.data)
        main.data = {
          ...main.data,
          plugin: {
            ...main.data.plugin,
            downloads_count: main.data.plugin.downloads_count + 1,
          },
        };
      toast.show('已打开下载地址', 'ok');
    }
  } catch (e) {
    tab?.close();
    if (current === epoch) toast.show((e as Error).message, 'error');
  } finally {
    if (current === epoch) installBusy.value = false;
  }
}
function recordVersion(version: string) {
  void api
    .post(`${path()}/install-record?version=${encodeURIComponent(version)}`)
    .catch(() => {});
}
async function copyCommand() {
  if (!plugin.value) return;
  try {
    await navigator.clipboard.writeText(
      `mofox plugin install ${plugin.value.plugin_id}@${selectedVersion.value}`,
    );
    toast.show('安装命令已复制', 'ok');
  } catch {
    toast.show('复制失败，请选中命令手动复制', 'error');
  }
}
function revealChapter() {
  activeTab.value = pluginChapter(route.hash);
  if (!route.hash.startsWith('#comment-')) return;
  const target = route.hash.slice('#comment-'.length);
  const thread = threads.value.find((item) =>
    item.replies.some((reply) => String(reply.id) === target),
  );
  if (thread) expanded.value = { ...expanded.value, [thread.root.id]: true };
}
watch(
  [pluginId, () => auth.viewer?.author_id],
  () => {
    epoch++;
    for (const resource of [main, versions, dependencies, comments, readme])
      resource.reset();
    activeTab.value = pluginChapter(route.hash);
    commentContent.value = '';
    mentionIds.value = [];
    expanded.value = {};
    submitting.value =
      subscriptionBusy.value =
      ratingBusy.value =
      installBusy.value =
      false;
    deleting.value = null;
    loadData();
  },
  { immediate: true },
);
watch(() => route.hash, revealChapter);
onBeforeUnmount(() => {
  epoch++;
});
</script>
<template>
  <CatalogFrame class="dossier-page">
    <nav class="catalog-breadcrumb" aria-label="位置">
      <router-link to="/browse">插件档案</router-link><span>/</span
      ><span>{{ plugin?.display_name || pluginId }}</span>
    </nav>
    <CatalogState
      :loading="main.loading"
      :error="main.error"
      :empty="!plugin"
      :count="2"
      @retry="loadData"
    >
      <template v-if="plugin">
        <p v-if="requestedVersion" class="catalog-empty-note" role="status">
          {{
            versions.loading
              ? '正在确认所选版本…'
              : selectedVersion
                ? `当前查看 v${selectedVersion}，下载和安装命令均对应此版本。`
                : `指定版本 v${requestedVersion} 暂不可获取，请重试版本信息或选择其他版本。`
          }}
          <router-link
            class="catalog-link"
            :to="{ name: 'plugin', params: { id: pluginId } }"
            >查看默认稳定版本</router-link
          >
        </p>
        <DossierLead
          class="plugin-identity" kind="插件"
          :title="plugin.display_name" :identifier="plugin.plugin_id"
          :summary="plugin.summary" :icon="plugin.icon_url"
          :author="plugin.owner_display_name || plugin.owner_login || plugin.owner_id"
          :author-id="plugin.owner_id" :updated-at="plugin.updated_at"
          :version="selectedVersion" :categories="plugin.categories" :tags="plugin.tags"
          category-route="market"
          :note="statusText(plugin.status) + ' · ' + trustLevelLabel(plugin.trust_level)" :license="plugin.license"
        >
          <template #actions>
            <nav class="plugin-lead-actions" :class="{ 'has-sticky-actions': selectedVersion }" aria-label="插件操作">
              <router-link class="btn" :to="sectionLink('#usage')"><AppIcon name="book" :size="16" />{{ guideLabel }}</router-link>
              <router-link class="btn btn-primary" :to="sectionLink('#get')"><AppIcon name="download" :size="16" />获取插件</router-link>
            </nav>
          </template>
        </DossierLead>
        <div class="catalog-dossier article-columns">
        <DossierNavigation
          :active="activeTab"
          :versions="versions.data.length"
          :comments="plugin.comments_count"
          kind="插件"
          :document-label="guideLabel"
        />
          <div class="catalog-main">
            <div
              v-show="activeTab === 'overview'"
              id="overview"
              class="detail-sections dossier-chapter"
            >
              <section class="catalog-panel">

                <h2 class="section-offset">功能说明</h2>
                <div class="catalog-document">
                  {{ plugin.description || plugin.summary }}
                </div>
                <div
                  v-if="plugin.categories?.length || plugin.tags?.length"
                  class="catalog-tags section-offset"
                >
                  <router-link
                    v-for="cat in plugin.categories || []"
                    :key="cat"
                    :to="{ name: 'market', query: { category: cat } }"
                    >{{ categoryLabel(cat) }}</router-link
                  ><router-link
                    v-for="tag in plugin.tags || []"
                    :key="tag"
                    :to="{ name: 'market', query: { tag } }"
                    >#{{ tag }}</router-link
                  >
                </div>
              </section>

              <section
                v-if="
                  dependencies.loading ||
                  dependencies.error ||
                  dependencies.data.length
                "
                class="catalog-panel"
                id="dependencies"
              >

                <h2 class="section-offset">依赖插件</h2>
                <CatalogState
                  :loading="dependencies.loading"
                  :error="dependencies.error"
                  :count="1"
                  @retry="loadDependencies"
                  ><div class="dependency-list">
                    <component
                      :is="dependency.exists_in_market ? 'router-link' : 'div'"
                      v-for="dependency in dependencies.data"
                      :key="dependency.plugin_id"
                      :to="
                        dependency.exists_in_market
                          ? `/plugin/${encodeURIComponent(dependency.plugin_id)}`
                          : undefined
                      "
                      class="dependency-row"
                      ><div>
                        <strong>{{
                          dependency.display_name || dependency.plugin_id
                        }}</strong
                        ><code>{{
                          dependency.version_spec || '未指定版本'
                        }}</code>
                      </div>
                      <span>{{
                        dependency.exists_in_market
                          ? '查看档案 ↗'
                          : '市场暂未收录'
                      }}</span></component
                    >
                  </div></CatalogState
                >
              </section>
              <section
                v-if="plugin.maintainers?.length"
                id="maintainers"
                class="catalog-panel"
              >
                <h2>共同维护</h2>
                <div class="catalog-tags">
                  <router-link
                    v-for="maintainer in plugin.maintainers"
                    :key="maintainer"
                    :to="`/author/${encodeURIComponent(maintainer)}`"
                    >{{ maintainer }} ↗</router-link
                  >
                </div>
              </section>
            </div>
            <section
              v-show="activeTab === 'readme'"
              id="readme"
              class="catalog-panel dossier-chapter documentation-panel"
            >

              <div id="usage" class="document-header plugin-guide-heading">
                <h2><AppIcon name="book" :size="20" />{{ guideLabel }}</h2>
                <router-link class="catalog-link" :to="sectionLink('#get')"><AppIcon name="download" :size="15" />获取插件</router-link>
              </div>
              <CatalogState
                :loading="readme.loading"
                :error="readme.error"
                :count="2"
                @retry="loadReadme"
                ><ReadmeDocument
                  v-if="documentHtml"
                  :html="documentHtml"
                  :reserved-ids="['usage', 'get']"
                />
              </CatalogState>
                <div v-if="!readme.loading && !documentHtml" class="plugin-author-guide">
                  <div v-if="authorDescription" class="catalog-document">{{ authorDescription }}</div>
                  <nav v-if="projectLinks.length" class="guide-sources" aria-label="作者项目链接">
                    <a v-for="link in projectLinks" :key="link.label" :href="link.href" target="_blank" rel="noopener noreferrer">
                      <AppIcon :name="link.icon" :size="15" />{{ link.label }} ↗
                    </a>
                  </nav>
                  <router-link v-if="!authorDescription && !projectLinks.length" class="catalog-link" :to="sectionLink('#get')">版本与兼容 ↗</router-link>
                </div>
            </section>
            <section
              v-show="activeTab === 'versions'"
              id="versions"
              class="catalog-panel dossier-chapter release-ledger"
            >

              <div class="document-header">
                <h2>版本记录</h2>
                <span>{{ versions.data.length }} 个版本</span>
              </div>
              <p class="catalog-muted">
                检查兼容信息，选择适合当前环境的版本。安装命令与获取操作始终对应所选版本。
              </p>
              <CatalogState
                :loading="versions.loading"
                :error="versions.error"
                :empty="!versions.data.length"
                :count="2"
                title="暂无公开版本"
                message="作者还没有发布可获取的版本。"
                @retry="loadVersions"
                ><article
                  v-for="version in versions.data"
                  :key="version.version"
                  class="release-row"
                  :class="{
                    'is-selected': selectedVersion === version.version,
                    'is-withdrawn': version.is_yanked,
                  }"
                  :id="`version-${version.version}`"
                >
                  <header>
                    <strong>v{{ version.version }}</strong
                    ><span
                      v-if="selectedVersion === version.version"
                      class="release-selected"
                      >当前获取版本</span
                    ><span
                      v-else-if="
                        !version.is_prerelease &&
                        !version.is_yanked &&
                        version.status === 'published'
                      "
                      class="release-stable"
                      >稳定版</span
                    ><span v-if="version.is_prerelease">预发布</span
                    ><span v-if="version.is_yanked">已撤回</span
                    ><time>{{ formatDate(version.published_at) }}</time>
                  </header>
                  <h3>{{ version.release_title || '版本发布' }}</h3>
                  <p>
                    API {{ version.plugin_api_version || '—' }} · 宿主 ≥
                    {{ version.min_host_version || '—'
                    }}{{
                      version.max_host_version
                        ? ` 且 ≤ ${version.max_host_version}`
                        : ''
                    }}<br />{{ formatBytes(version.file_size) }} ·
                    {{ formatNumber(version.download_count) }} 次下载 ·
                    {{
                      version.supported_platforms?.join(' / ') || '未限制平台'
                    }}
                  </p>
                  <div class="catalog-actions">
                    <router-link
                      v-if="
                        !version.is_yanked &&
                        version.status === 'published' &&
                        selectedVersion !== version.version
                      "
                      class="btn btn-sm"
                      :to="{
                        name: 'plugin',
                        params: { id: pluginId },
                        query: { ...route.query, version: version.version },
                        hash: '#versions',
                      }"
                      >设为获取版本</router-link
                    >
                    <a
                      v-if="version.release_url"
                      class="btn btn-sm"
                      :href="version.release_url"
                      target="_blank"
                      rel="noopener noreferrer"
                      >发布说明 ↗</a
                    ><a
                      v-if="
                        version.asset_download_url &&
                        !version.is_yanked &&
                        version.status === 'published'
                      "
                      class="btn btn-primary btn-sm"
                      :href="version.asset_download_url"
                      target="_blank"
                      rel="noopener noreferrer"
                      @click="recordVersion(version.version)"
                      ><AppIcon name="download" :size="14" /> 获取此版本</a
                    >
                  </div>
                </article></CatalogState
              >
            </section>
            <section
              v-show="activeTab === 'comments'"
              id="comments"
              class="catalog-panel dossier-chapter discussion-panel"
            >
              <div class="catalog-kicker">
                第四章　讨论 · {{ plugin.comments_count }} 条
              </div>
              <h2 class="section-offset">交流使用体验</h2>
              <form
                v-if="auth.isAuthenticated"
                class="comment-form"
                @submit.prevent="submitComment"
              >
                <MentionInput
                  v-model="commentContent"
                  :maxlength="4000"
                  :disabled="submitting"
                  placeholder="分享体验或提出问题，支持 @提及作者…"
                  @update:mentioned-author-ids="mentionIds = $event"
                />
                <div class="comment-form-bottom">
                  <small>已识别 {{ mentionIds.length }} 位提及作者</small
                  ><button
                    class="btn btn-primary btn-sm"
                    :disabled="submitting || !commentContent.trim()"
                  >
                    {{ submitting ? '发布中…' : '发布评论' }}
                  </button>
                </div>
              </form>
              <div v-else class="catalog-empty-note">
                {{
                  auth.loading
                    ? '正在确认登录状态…'
                    : '登录后，一起交流插件的使用体验。'
                }}
                <a
                  v-if="!auth.loading"
                  class="catalog-link"
                  :href="auth.getLoginUrl()"
                  >GitHub 登录 ↗</a
                >
              </div>
              <CatalogState
                :loading="comments.loading"
                :error="comments.error"
                :empty="!comments.data.length"
                :count="2"
                title="讨论从这里开始"
                message="还没有评论，欢迎分享你的体验。"
                @retry="loadComments"
                ><div v-for="thread in threads" :key="thread.root.id">
                  <CatalogComment
                    :comment="thread.root"
                    :removable="canRemove(thread.root)"
                    :deleting="deleting === thread.root.id"
                    @remove="removeComment(thread.root.id)"
                  />
                  <div v-if="thread.replies.length" class="comment-replies">
                    <CatalogComment
                      v-for="reply in expanded[thread.root.id]
                        ? thread.replies
                        : thread.replies.slice(0, 3)"
                      :key="reply.id"
                      :comment="reply"
                      :removable="canRemove(reply)"
                      :deleting="deleting === reply.id"
                      @remove="removeComment(reply.id)"
                    /><button
                      v-if="thread.replies.length > 3"
                      class="btn btn-ghost btn-sm"
                      @click="
                        expanded[thread.root.id] = !expanded[thread.root.id]
                      "
                    >
                      {{
                        expanded[thread.root.id]
                          ? '收起回复'
                          : `展开其余 ${thread.replies.length - 3} 条回复`
                      }}
                    </button>
                  </div>
                </div></CatalogState
              >
            </section>
          </div>
          <aside class="catalog-aside">
            <section id="get" class="catalog-panel acquisition">
              <div class="acquisition-label">
                <span>获取插件</span><small>安装与兼容</small>
              </div>
              <h2 class="section-offset">
                {{ selectedVersion ? `v${selectedVersion}` : '暂无可获取版本' }}
              </h2>
              <p class="catalog-muted">
                {{
                  selectedVersion
                    ? `发布于 ${formatRelative(latestVersion?.published_at || plugin.latest_version_published_at)}`
                    : '发布后即可在这里获取'
                }}
              </p>
              <div class="catalog-actions">
                <button
                  class="btn btn-primary"
                  :disabled="!selectedVersion || installBusy"
                  @click="install"
                >
                  <AppIcon name="download" :size="16" />
                  {{ installBusy ? '正在准备下载…' : '下载插件' }}</button
                ><button
                  class="btn"
                  :disabled="subscriptionBusy || auth.loading"
                  @click="subscribe"
                >
                  {{
                    subscriptionBusy
                      ? '正在更新…'
                      : subscribed
                        ? '已订阅更新 ✓'
                        : '订阅更新 ＋'
                  }}
                </button>
              </div>
              <div v-if="selectedVersion" class="install-command">
                <code
                  >mofox plugin install {{ plugin.plugin_id }}@{{
                    selectedVersion
                  }}</code
                ><button @click="copyCommand" aria-label="复制安装命令">
                  复制
                </button>
              </div>
              <a
                v-if="!auth.isAuthenticated && !auth.loading"
                class="login-link"
                :href="auth.getLoginUrl()"
                >登录后可订阅、评分与评论 ↗</a
              >
              <div class="catalog-stat-row">
                <div>
                  <b>{{ formatNumber(plugin.downloads_count) }}</b
                  ><span>累计下载</span>
                </div>
                <div>
                  <b>{{ formatNumber(plugin.likes_count) }}</b
                  ><span>订阅人数</span>
                </div>
                <div>
                  <b>{{
                    plugin.rating_count
                      ? Number(plugin.rating_avg).toFixed(1)
                      : '—'
                  }}</b
                  ><span>{{ plugin.rating_count }} 条评分</span>
                </div>
              </div>
              <dl class="catalog-facts">
                <div>
                  <dt>插件 API</dt>
                  <dd>
                    {{
                      latestVersion?.plugin_api_version ||
                      (versions.loading ? '正在读取' : '未提供')
                    }}
                  </dd>
                </div>
                <div>
                  <dt>宿主版本</dt>
                  <dd>
                    {{
                      latestVersion?.min_host_version
                        ? `≥ ${latestVersion.min_host_version}${latestVersion.max_host_version ? `，≤ ${latestVersion.max_host_version}` : ''}`
                        : '兼容性待确认'
                    }}
                  </dd>
                </div>
                <div>
                  <dt>支持平台</dt>
                  <dd>
                    {{
                      latestVersion?.supported_platforms?.join(' / ') ||
                      '请查看发布说明'
                    }}
                  </dd>
                </div>
              </dl>
              <div v-if="versions.error" class="catalog-muted section-offset">
                版本信息暂不可用，<button
                  class="catalog-link"
                  @click="loadVersions"
                >
                  重试
                </button>
              </div>
              <div class="external-links">
                <a
                  :href="plugin.repository_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  >代码仓库 ↗</a
                ><a
                  v-if="plugin.homepage"
                  :href="plugin.homepage"
                  target="_blank"
                  rel="noopener noreferrer"
                  >项目主页 ↗</a
                >
              </div>
              <RiskWarning kind="panel" />
            </section>
            <section class="catalog-panel community-rating">

              <h2 class="section-offset">社区评分</h2>
              <p class="catalog-muted">
                {{ plugin.rating_count }} 位用户的真实反馈
              </p>
              <div
                v-for="row in ratingRows"
                :key="row.score"
                class="catalog-rating-row"
                :aria-label="`${row.score}星：${row.count}人`"
              >
                <span>{{ row.score }}★</span
                ><span class="catalog-rating-track"
                  ><i :style="{ width: `${row.percent}%` }"></i></span
                ><span>{{ row.count }}</span>
              </div>
              <div class="catalog-stars">
                <button
                  v-for="n in 5"
                  :key="n"
                  :class="{ active: (rating?.viewer_rating || 0) >= n }"
                  :aria-label="`评 ${n} 星`"
                  :aria-pressed="rating?.viewer_rating === n"
                  :disabled="ratingBusy || auth.loading"
                  @click="rate(n)"
                >
                  ★</button
                ><button
                  v-if="rating?.viewer_rating"
                  class="clear-rating"
                  :disabled="ratingBusy"
                  @click="rate(null)"
                >
                  清除
                </button>
              </div>
              <p class="catalog-caption">
                {{
                  rating?.viewer_rating
                    ? `我的评分：${rating.viewer_rating} 星`
                    : '点击星星，为插件评分'
                }}
              </p>
            </section>
          </aside>
        </div>
        <RecommendationSection
          placement="detail"
          :context-plugin-id="plugin.plugin_id"
        />
        <div v-if="selectedVersion" class="mobile-acquire">
          <span
            >{{ plugin.display_name
            }}<small>v{{ selectedVersion }}</small></span
          ><div class="mobile-acquire-links">
            <router-link class="btn" :to="sectionLink('#usage')"><AppIcon name="book" :size="15" />{{ guideLabel }}</router-link>
            <button
            class="btn btn-primary"
            :disabled="installBusy"
            @click="install"
          >
            <AppIcon name="download" :size="15" />{{ installBusy ? '准备中…' : '下载插件' }}
          </button>
          </div>
        </div>
      </template>
    </CatalogState>
  </CatalogFrame>
</template>
<style scoped>
.plugin-lead-actions,
.mobile-acquire-links,
.plugin-guide-heading h2,
.plugin-guide-heading a,
.guide-sources,
.guide-sources a {
  display: flex;
  align-items: center;
  gap: 8px;
}
.plugin-lead-actions { margin-top: 18px; flex-wrap: wrap; }
.plugin-lead-actions .btn { min-height: 40px; }
.plugin-guide-heading h2 { margin: 0; }
.plugin-guide-heading a, .guide-sources a { font-size: 12px; color: var(--blue-700); }
.plugin-author-guide { display: grid; gap: 18px; }
.guide-sources { gap: 12px 20px; flex-wrap: wrap; }
.plugin-guide-heading, .acquisition { scroll-margin-top: calc(var(--topbar-h, 64px) + 84px); }
.mobile-acquire-links { flex: none; }
@media (min-width: 1181px) {
  .plugin-guide-heading, .acquisition { scroll-margin-top: calc(var(--topbar-h, 64px) + 22px); }
}
@media (max-width: 620px) {
  .plugin-lead-actions.has-sticky-actions { display: none; }
  .mobile-acquire-links { gap: 6px; }
  .mobile-acquire-links .btn { min-height: 40px; padding-inline: 9px; gap: 5px; font-size: 12px; }
}
.detail-sections {
  display: grid;
  gap: 22px;
}
.section-offset {
  margin-top: 18px !important;
}
.release-row {
  padding: 24px 0;
  border-bottom: 1px solid var(--line);
}
.release-row:last-child {
  border: 0;
  padding-bottom: 0;
}
.release-row header {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  font: 12px var(--font-mono);
}
.release-row header strong {
  font-size: 20px;
  color: var(--blue-700);
}
.release-row header > span {
  color: var(--warning-ink);
  font-size: 10px;
}
.release-row time {
  margin-left: auto;
  color: var(--ink-500);
  font-size: 11px;
}
.release-row h3 {
  margin: 15px 0 7px !important;
  font-size: 14px !important;
}
.release-row p {
  font-size: 12px;
  color: var(--ink-500);
  margin: 0 0 15px;
}
.dependency-list {
  display: grid;
  gap: 10px;
}
.dependency-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--line);
  font-size: 12px;
}
.dependency-row > div {
  display: grid;
  gap: 5px;
  min-width: 0;
}
.dependency-row code {
  font-size: 10px;
  overflow-wrap: anywhere;
}
.dependency-row > span {
  font-size: 10px;
  color: var(--blue-600);
  flex: none;
}
.comment-form {
  display: grid;
  gap: 12px;
  margin-bottom: 22px;
}
.comment-form-bottom {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}
.comment-form-bottom small {
  font-size: 11px;
  color: var(--ink-500);
}
.comment-replies {
  margin-left: 46px;
}
.install-command {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  margin-top: 10px;
  background: var(--surface-soft);
  border: 1px solid var(--line);
  border-inline-start: 2px solid var(--blue-500);
  font-size: 12px;
}
.install-command code {
  min-width: 0;
  flex: 1;
  overflow-wrap: anywhere;
  background: none;
  padding: 0;
  white-space: normal;
  line-height: 1.8;
}
.install-command button {
  min-height: 34px;
  min-width: 40px;
  padding-inline: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--blue-600);
  flex: none;
}
.external-links {
  display: flex;
  gap: 18px;
  margin-top: 20px;
  font-size: 12px;
  color: var(--blue-600);
}
.acquisition :deep(.risk-warning) {
  margin-top: 22px;
  padding: 14px;
  border: 1px solid var(--line);
  background: var(--surface-soft);
  font-size: 11px;
  color: var(--ink-500);
}
.acquisition :deep(.risk-warning p) {
  font-size: 11px;
  line-height: 1.7;
  margin: 7px 0;
}
.acquisition :deep(.risk-warning strong) {
  font-size: 11px;
  color: var(--ink-700);
}
.catalog-stars .clear-rating {
  font-size: 11px;
  padding: 6px;
  margin-left: 6px;
}
.login-link {
  display: block;
  font-size: 11px;
  color: var(--blue-600);
  margin-top: 13px;
}
.mobile-acquire {
  display: none;
}
@media (max-width: 620px) {
  .mobile-acquire {
    display: flex;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 29;
    padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
    gap: 14px;
    align-items: center;
    justify-content: space-between;
    background: var(--surface);
    border-top: 1px solid var(--line);
  }
  .mobile-acquire > span {
    min-width: 0;
    font-size: 12px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .mobile-acquire small {
    display: block;
    font: 10px var(--font-mono);
    margin-top: 4px;
    color: var(--ink-500);
  }
  .mobile-acquire .btn {
    flex: none;
  }
  .comment-replies {
    margin-left: 22px;
  }
}
</style>
