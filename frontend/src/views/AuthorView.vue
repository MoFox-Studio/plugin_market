<script setup lang="ts">
import { computed, ref, watch, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import api from '@/api';
import { useAuthStore } from '@/stores/auth';
import { useToastStore } from '@/stores/toast';
import { formatNumber, formatRelative } from '@/utils/format';
import type {
  AuthorFollowState,
  AuthorProfile,
  PinnedPlugin,
  Plugin,
} from '@/types';
import PluginCard from '@/components/PluginCard.vue';
import CatalogFrame from '@/components/catalog/CatalogFrame.vue';
import CatalogState from '@/components/catalog/CatalogState.vue';
import { useCatalogResource } from '@/components/catalog/useCatalogResource';
const props = defineProps<{ id: string }>();
const route = useRoute(),
  router = useRouter(),
  auth = useAuthStore(),
  toast = useToastStore();
const profile = useCatalogResource<AuthorProfile | null>(() => null),
  pins = useCatalogResource<PinnedPlugin[]>(() => []),
  follow = useCatalogResource<AuthorFollowState | null>(() => null);
const published = useCatalogResource(() => ({ items: [] as Plugin[], total: 0, loadedPage: 0 }));
const initialWorksLoading = computed(() => published.loading && !published.data.loadedPage);
const followBusy = ref(false),
  brokenAvatar = ref(false),
  pageSize = 21;
const page = computed(() => {
  const value = Number(route.query.page);
  return Number.isSafeInteger(value) && value > 0 ? value : 1;
});
const totalPages = computed(() =>
  Math.max(1, Math.ceil(published.data.total / pageSize)),
);
const identity = computed(
  () =>
    published.data.items.find((item) => item.owner_id === props.id) ||
    pins.data.find((item) => item.plugin?.owner_id === props.id)?.plugin,
);
const isOwnPage = computed(() => auth.viewer?.author_id === props.id);
const displayName = computed(() =>
  isOwnPage.value
    ? auth.viewer?.display_name || auth.viewer?.github_login || props.id
    : identity.value?.owner_display_name ||
      identity.value?.owner_login ||
      props.id,
);
const avatarUrl = computed(() =>
  isOwnPage.value ? auth.viewer?.avatar_url : identity.value?.owner_avatar_url,
);
const login = computed(() =>
  isOwnPage.value ? auth.viewer?.github_login : identity.value?.owner_login,
);
const cover = computed(() =>
  profile.data?.background_image_url
    ? {
        backgroundImage: `url(${JSON.stringify(profile.data.background_image_url)})`,
      }
    : {},
);
const pageTotals = computed(() =>
  published.data.items.reduce(
    (total, item) => ({
      subscriptions: total.subscriptions + Number(item.likes_count || 0),
      downloads: total.downloads + Number(item.downloads_count || 0),
    }),
    { subscriptions: 0, downloads: 0 },
  ),
);
const pinned = computed(() => pins.data.filter((item) => item.plugin));
let epoch = 0;
function loadProfile() {
  const id = props.id;
  return profile.load(() =>
    api.get(`/api/v1/authors/${encodeURIComponent(id)}/profile`),
  );
}
function loadPins() {
  const id = props.id;
  return pins.load(() =>
    api.get<PinnedPlugin[]>(`/api/v1/authors/${encodeURIComponent(id)}/pins`),
  );
}
function loadFollow() {
  const id = props.id;
  return follow.load(() => api.authors.followState(id));
}
async function loadPublished() {
  const id = props.id,
    currentPath = route.fullPath,
    requestedPage = page.value;
  const query = new URLSearchParams({
    author_id: id,
    limit: String(pageSize),
    offset: String((page.value - 1) * pageSize),
    sort: 'popular',
  });
  await published.load(async () => ({
    ...await api.get<{ items: Plugin[]; total: number }>(`/api/v1/plugins?${query}`),
    loadedPage: requestedPage,
  }));
  if (
    !published.loading && !published.error &&
    route.fullPath === currentPath &&
    page.value > totalPages.value
  )
    await router.replace({
      query: {
        ...route.query,
        page: totalPages.value > 1 ? String(totalPages.value) : undefined,
      },
    });
}
function loadAuthor() {
  void loadProfile();
  void loadPins();
  void loadFollow();
}
function setPage(value: number) {
  void router.push({
    query: { ...route.query, page: value > 1 ? String(value) : undefined },
  });
}
async function toggleFollow() {
  if (followBusy.value) return;
  if (!auth.isAuthenticated) {
    toast.show('登录后即可关注作者', 'error');
    return;
  }
  const id = props.id,
    current = epoch;
  followBusy.value = true;
  try {
    const result = await api.authors.toggleFollow(id);
    if (current !== epoch) return;
    follow.data = result;
    toast.show(result.following ? '已关注作者' : '已取消关注', 'ok');
  } catch (error) {
    if (current === epoch) toast.show((error as Error).message, 'error');
  } finally {
    if (current === epoch) followBusy.value = false;
  }
}
watch(
  [() => props.id, () => auth.viewer?.author_id],
  () => {
    epoch++;
    profile.reset();
    pins.reset();
    follow.reset();
    followBusy.value = brokenAvatar.value = false;
    loadAuthor();
  },
  { immediate: true },
);
watch(
  [() => props.id, () => auth.viewer?.author_id, page],
  ([id, viewer], previous) => {
    if (id !== previous?.[0] || viewer !== previous?.[1]) published.reset();
    void loadPublished();
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  epoch++;
});
</script>
<template>
  <CatalogFrame class="author-edition">
    <nav class="catalog-breadcrumb" aria-label="位置">
      <router-link to="/browse">插件档案</router-link><span>/</span
      ><span>创作者档案</span>
    </nav>
    <CatalogState
      :loading="profile.loading"
      :error="profile.error"
      :count="1"
      @retry="loadProfile"
    >
      <header class="portrait-spread">
        <figure class="portrait-plate">
          <div class="portrait-image" :class="{ 'has-cover': !!profile.data?.background_image_url }" :style="cover">
            <div class="portrait-avatar">
              <img v-if="avatarUrl && !brokenAvatar" :src="avatarUrl" alt="" @error="brokenAvatar = true" />
              <span v-else aria-hidden="true">{{ displayName?.[0]?.toUpperCase() || 'A' }}</span>
            </div>
          </div>
          <figcaption><span>创作者图录</span><span>{{ login ? '@' + login : props.id }}</span></figcaption>
        </figure>
        <div class="portrait-copy">
          <p class="portrait-section">社区人物</p>
          <h1>{{ displayName }}</h1>
          <div class="portrait-bio">
            <span>作者简介</span>
            <p>{{ profile.data?.bio || '作者尚未填写个人简介。' }}</p>
          </div>
          <div class="author-actions">
            <router-link
              v-if="isOwnPage"
              class="btn btn-primary"
              to="/me/profile"
              >编辑个人资料 ↗</router-link
            ><button
              v-else
              class="btn btn-primary"
              :disabled="
                followBusy || follow.loading || !!follow.error || auth.loading
              "
              @click="toggleFollow"
            >
              {{
                followBusy
                  ? '正在更新…'
                  : follow.data?.following
                    ? '已关注 ✓'
                    : '关注创作者 ＋'
              }}</button
            ><button
              v-if="follow.error"
              class="catalog-link"
              @click="loadFollow"
            >
              关注状态加载失败，重试</button
            ><span v-else class="catalog-caption">{{
              follow.loading
                ? '正在读取关注信息'
                : `${formatNumber(follow.data?.followers_count || 0)} 位关注者`
            }}</span
            ><a
              v-if="!auth.isAuthenticated && !auth.loading"
              class="catalog-link"
              :href="auth.getLoginUrl()"
              >GitHub 登录 ↗</a
            >
          </div>
        </div>
      </header>
    </CatalogState>
    <section v-if="pins.loading || pins.error || pinned.length">
      <div class="catalog-section-heading">
        <div>

          <h2>作者精选</h2>
        </div>
        <span class="catalog-caption"
          >{{ pinned.length }} 件置顶作品</span
        >
      </div>
      <CatalogState
        :loading="pins.loading"
        :error="pins.error"
        cards
        :count="3"
        @retry="loadPins"
        ><div class="author-pins">
          <article v-for="(pin, index) in pinned" :key="pin.plugin_id" class="pin-entry">
            <p v-if="pin.pinned_reason" class="pin-note"><span>荐语</span>{{ pin.pinned_reason }}</p>
            <PluginCard v-if="pin.plugin" :plugin="pin.plugin" :number="index + 1" /><span
              class="catalog-caption"
              >精选于 {{ formatRelative(pin.pinned_at) }}</span
            >
          </article>
        </div></CatalogState
      >
    </section>
    <section class="author-works" :aria-busy="published.loading">
      <div class="catalog-section-heading">
        <div>

          <h2>
            全部作品 <small>{{ published.data.total }}</small>
          </h2>
        </div>
        <span class="catalog-caption" aria-live="polite">{{ published.loading && !initialWorksLoading ? '正在更新作品…' : '按热度排列' }}</span>
      </div>
        <div class="author-stats">
          <div>
            <strong>{{
              published.loading || published.error ? '—' : formatNumber(published.data.total)
            }}</strong
            ><span>公开插件</span>
          </div>
          <div>
            <strong>{{
              published.loading || published.error ? '—' : formatNumber(pageTotals.subscriptions)
            }}</strong
            ><span>本页作品订阅</span>
          </div>
          <div>
            <strong>{{
              published.loading || published.error ? '—' : formatNumber(pageTotals.downloads)
            }}</strong
            ><span>本页作品下载</span>
          </div>
        </div>
      <CatalogState
        :loading="initialWorksLoading"
        :error="published.error"
        :empty="!published.data.items.length"
        cards
        title="暂未发布公开插件"
        message="新的作品发布后，会出现在这里。"
        @retry="loadPublished"
        ><div class="catalog-grid edition-index">
          <PluginCard
            v-for="(plugin, index) in published.data.items"
            :key="plugin.plugin_id"
            :plugin="plugin"
            :number="(published.data.loadedPage - 1) * pageSize + index + 1"
          />
        </div>
        <nav
          v-if="totalPages > 1"
          class="catalog-pagination"
          aria-label="作者作品分页"
        >
          <button
            class="btn btn-sm"
            :disabled="published.loading || page === 1"
            @click="setPage(page - 1)"
          >
            ← 上一页</button
          ><span>{{ published.data.loadedPage || page }} / {{ totalPages }}</span
          ><button
            class="btn btn-sm"
            :disabled="published.loading || page >= totalPages"
            @click="setPage(page + 1)"
          >
            下一页 →
          </button>
        </nav></CatalogState
      >
    </section>
  </CatalogFrame>
</template>
<style scoped>
.portrait-spread { display: grid; grid-template-columns: minmax(190px, .6fr) minmax(0, 1fr); gap: clamp(24px, 5vw, 70px); align-items: center; padding: 12px 0 32px; border-bottom: 3px double var(--ink-500); }
.portrait-plate { min-width: 0; margin: 0; }
.portrait-image { display: grid; place-items: center; aspect-ratio: 4 / 3; padding: 22px; background: repeating-linear-gradient(135deg, transparent 0 7px, var(--line-soft) 7px 8px), var(--surface-soft); }
.portrait-image.has-cover { background-position: center; background-size: cover; }
.portrait-avatar { width: 52%; aspect-ratio: 1; display: grid; place-items: center; color: var(--blue-700); background: var(--surface); outline: 6px solid var(--surface); font: 800 clamp(40px, 6vw, 82px)/1 var(--font-editorial); }
.portrait-avatar img { width: 100%; height: 100%; object-fit: cover; }
.portrait-plate figcaption { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px; padding: 9px 0; font-size: 11px; color: var(--ink-500); overflow-wrap: anywhere; }
.portrait-copy { min-width: 0; }
.portrait-section { margin: 0 0 10px; font-size: 12px; color: var(--blue-700); letter-spacing: .15em; }
.portrait-copy h1 { margin: 0; font: 800 clamp(38px, 5.3vw, 74px)/1.15 var(--font-editorial); color: var(--ink-900); overflow-wrap: anywhere; }
.portrait-bio { margin: 22px 0; }
.portrait-bio>span, .pin-note>span { display: block; font-size: 11px; color: var(--blue-700); margin-bottom: 6px; }
.portrait-bio p { margin: 0; max-width: 56ch; font: 400 clamp(16px, 1.55vw, 20px)/1.85 var(--font-reading); white-space: pre-line; overflow-wrap: anywhere; }
.author-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 10px 16px; font-size: 12px; }
.author-stats { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 26px; padding: 8px 0 18px; border-bottom: 1px solid var(--line); }
.author-stats>div { display: flex; align-items: baseline; gap: 8px; }
.author-stats strong { font: 700 21px/1.2 var(--font-editorial); }
.author-stats span, .pin-entry>.catalog-caption { font-size: 11px; color: var(--ink-500); }
.author-pins { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 210px), 1fr)); gap: 20px 32px; }
.pin-entry { min-width: 0; }
.pin-note { margin: 0; padding: 10px 14px; border-left: 2px solid var(--blue-500); background: var(--surface-soft); font: 400 15px/1.7 var(--font-reading); overflow-wrap: anywhere; }
.pin-entry>.catalog-caption { display: block; margin-top: 8px; }
.author-edition :deep(.catalog-section-heading h2) { font: 800 clamp(23px, 2.5vw, 34px)/1.3 var(--font-editorial); }
@media(max-width: 680px) {
  .portrait-spread { grid-template-columns: 1fr; gap: 16px; }
  .portrait-image { max-height: 220px; }
  .portrait-avatar { width: auto; height: 85%; }
  .portrait-copy h1 { font-size: 40px; }
  .portrait-bio { margin: 14px 0 18px; }
}
</style>
