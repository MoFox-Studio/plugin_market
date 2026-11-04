<script setup lang="ts">
import { useMarketDialog } from '@/composables/useMarketDialog';
const { confirm: confirmAction, prompt: promptAction } = useMarketDialog();
import { computed, ref, watch, onBeforeUnmount } from 'vue';
import { useRoute } from 'vue-router';
import api from '@/api';
import { useAuthStore } from '@/stores/auth';
import { useToastStore } from '@/stores/toast';
import {
  categoryLabel,
  formatBytes,
  formatDate,
  formatNumber,
  formatRelative,
} from '@/utils/format';
import type {
  Skill,
  SkillVersion,
  SkillComment,
  SkillRatingInfo,
} from '@/types';
import CatalogFrame from '@/components/catalog/CatalogFrame.vue';
import DossierNavigation from '@/components/catalog/DossierNavigation.vue';
import DossierLead from '@/components/catalog/DossierLead.vue';
import ReadmeDocument from '@/components/catalog/ReadmeDocument.vue';
import { dossierChapter } from '@/components/catalog/dossierChapter';
import AppIcon from '@/components/AppIcon.vue';
import CatalogState from '@/components/catalog/CatalogState.vue';
import CatalogComment from '@/components/catalog/CatalogComment.vue';
import { useCatalogResource } from '@/components/catalog/useCatalogResource';
const route = useRoute(),
  auth = useAuthStore(),
  toast = useToastStore();
const skillId = computed(() => String(route.params.id));
const main = useCatalogResource<Skill | null>(() => null),
  versions = useCatalogResource<SkillVersion[]>(() => []),
  comments = useCatalogResource<SkillComment[]>(() => []),
  rating = useCatalogResource<SkillRatingInfo>(() => ({}));
const skill = computed(() => main.data),
  tab = ref('overview'),
  comment = ref(''),
  likeBusy = ref(false),
  ratingBusy = ref(false),
  commentBusy = ref(false),
  deleting = ref<number | null>(null);
const latestVersion = computed(
  () =>
    versions.data.find((v) => v.version === skill.value?.latest_version) ||
    versions.data[0],
);
const downloadUrl = computed(() =>
  skill.value?.latest_version
    ? api.skills.downloadUrl(skillId.value, skill.value.latest_version)
    : '',
);
const ratingRows = computed(() => {
  const total = Object.values(rating.data.distribution || {}).reduce(
    (sum, count) => sum + Number(count),
    0,
  );
  return [5, 4, 3, 2, 1].map((score) => {
    const count = Number(rating.data.distribution?.[String(score)] || 0);
    return {
      score,
      count,
      percent: total ? Math.min(100, (count / total) * 100) : 0,
    };
  });
});
let epoch = 0;
function loadVersions() {
  const id = skillId.value;
  return versions.load(() =>
    api.skills.versions(id).then((res) => res.items || []),
  );
}
function loadComments() {
  const id = skillId.value;
  return comments.load(() =>
    api.skills.comments(id).then((res) => res.items || []),
  );
}
function loadRating() {
  const id = skillId.value;
  return rating.load(() => api.skills.rating(id));
}
function load() {
  const id = skillId.value;
  void main.load(() => api.skills.get(id));
  void loadVersions();
  void loadComments();
  void loadRating();
}
function requireLogin() {
  if (auth.isAuthenticated) return false;
  toast.show('登录后即可参与社区互动', 'error');
  return true;
}
async function toggleLike() {
  if (likeBusy.value || requireLogin()) return;
  const id = skillId.value,
    current = epoch;
  likeBusy.value = true;
  try {
    const result = await api.skills.toggleLike(id);
    if (current === epoch && main.data)
      main.data = {
        ...main.data,
        viewer_has_liked: result.liked,
        likes_count: Math.max(
          0,
          main.data.likes_count + (result.liked ? 1 : -1),
        ),
      };
  } catch (e) {
    if (current === epoch) toast.show((e as Error).message, 'error');
  } finally {
    if (current === epoch) likeBusy.value = false;
  }
}
async function rate(score: number | null) {
  if (ratingBusy.value || requireLogin()) return;
  const id = skillId.value,
    current = epoch;
  ratingBusy.value = true;
  try {
    if (score === null) await api.skills.deleteRating(id);
    else await api.skills.postRating(id, score);
    if (current !== epoch) return;
    await loadRating();
    const updated = await api.skills.get(id);
    if (current === epoch) {
      main.data = updated;
      toast.show(score === null ? '已清除评分' : '感谢你的评分', 'ok');
    }
  } catch (e) {
    if (current === epoch) toast.show((e as Error).message, 'error');
  } finally {
    if (current === epoch) ratingBusy.value = false;
  }
}
async function postComment() {
  if (commentBusy.value || !comment.value.trim() || requireLogin()) return;
  const id = skillId.value,
    current = epoch,
    content = comment.value.trim();
  commentBusy.value = true;
  try {
    await api.skills.postComment(id, { content });
    if (current !== epoch) return;
    comment.value = '';
    if (main.data)
      main.data = {
        ...main.data,
        comments_count: main.data.comments_count + 1,
      };
    toast.show('评论已发布', 'ok');
    await loadComments();
  } catch (e) {
    if (current === epoch) toast.show((e as Error).message, 'error');
  } finally {
    if (current === epoch) commentBusy.value = false;
  }
}
function canRemove(item: SkillComment) {
  return (
    !!auth.viewer &&
    (auth.viewer.author_id === item.author.author_id || auth.isAdmin)
  );
}
async function removeComment(commentId: number) {
  if (deleting.value !== null || !(await confirmAction('确定删除这条评论吗？')))
    return;
  const id = skillId.value,
    current = epoch;
  deleting.value = commentId;
  try {
    await api.skills.deleteComment(id, commentId);
    if (current !== epoch) return;
    await loadComments();
    const updated = await api.skills.get(id);
    if (current === epoch) main.data = updated;
  } catch (e) {
    if (current === epoch) toast.show((e as Error).message, 'error');
  } finally {
    if (current === epoch) deleting.value = null;
  }
}
function recordDownload() {
  const id = skillId.value,
    current = epoch;
  void api.skills
    .recordInstall(id)
    .then((result) => {
      if (current === epoch && main.data)
        main.data = { ...main.data, download_count: result.download_count };
    })
    .catch(() => {});
}
watch(
  [skillId, () => auth.viewer?.author_id],
  () => {
    epoch++;
    for (const resource of [main, versions, comments, rating]) resource.reset();
    comment.value = '';
    tab.value = dossierChapter(route.hash);
    likeBusy.value =
      ratingBusy.value =
      commentBusy.value =
      false;
    deleting.value = null;
    load();
  },
  { immediate: true },
);
watch(
  () => route.hash,
  () => {
    tab.value = dossierChapter(route.hash);
  },
);
onBeforeUnmount(() => {
  epoch++;
});
</script>
<template>
  <CatalogFrame class="dossier-page">
    <nav class="catalog-breadcrumb" aria-label="位置">
      <router-link to="/skills">技能资料库</router-link><span>/</span
      ><span>{{ skill?.display_name || skillId }}</span>
    </nav>
    <CatalogState
      :loading="main.loading"
      :error="main.error"
      :empty="!skill"
      :count="2"
      @retry="load"
      ><template v-if="skill">
        <DossierLead
          class="skill-identity" kind="技能"
          :title="skill.display_name" :identifier="skill.skill_id"
          :summary="skill.description" :icon="skill.icon_url"
          :author="skill.owner_display_name || skill.owner_login || skill.owner_id"
          :author-id="skill.owner_id" :updated-at="skill.updated_at"
          :version="skill.latest_version" :categories="skill.categories" :tags="skill.tags"
          category-route="skills"
        />
        <div class="catalog-dossier article-columns">
        <DossierNavigation
          :active="tab"
          :versions="versions.data.length"
          :comments="skill.comments_count"
          kind="技能"
        />
          <div class="catalog-main">
            <section
              v-show="tab === 'overview'"
              id="overview"
              class="catalog-panel dossier-chapter"
            >

              <h2 class="section-offset">能力说明</h2>
              <div class="catalog-document">
                {{ skill.description || '作者尚未提供说明。' }}
              </div>

              <div
                v-if="skill.categories?.length || skill.tags?.length"
                class="catalog-tags section-offset"
              >
                <router-link
                  v-for="cat in skill.categories || []"
                  :key="cat"
                  :to="{ name: 'skills', query: { category: cat } }"
                  >{{ categoryLabel(cat) }}</router-link
                ><router-link
                  v-for="tag in skill.tags || []"
                  :key="tag"
                  :to="{ name: 'skills', query: { tag } }"
                  >#{{ tag }}</router-link
                >
              </div>
            </section>
            <section
              v-show="tab === 'readme'"
              id="readme"
              class="catalog-panel dossier-chapter documentation-panel"
            >

              <div class="document-header">
                <h2>SKILL.md</h2>
                <span>作者原文</span>
              </div>
              <ReadmeDocument
                :source="
                  skill.readme_markdown ||
                  skill.description ||
                  '作者尚未提供详细说明。'
                "
              />
            </section>
            <section
              v-show="tab === 'versions'"
              id="versions"
              class="catalog-panel dossier-chapter release-ledger"
            >

              <div class="document-header">
                <h2>版本记录</h2>
                <span>{{ versions.data.length }} 个版本</span>
              </div>
              <p class="catalog-muted">
                按更新时间阅读迭代记录，获取与你的 MoFox 兼容的技能包。
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
                  class="skill-release"
                  :class="{
                    'is-selected': version.version === skill.latest_version,
                  }"
                  :id="`version-${version.version}`"
                >
                  <header>
                    <strong>v{{ version.version }}</strong
                    ><span
                      v-if="version.version === skill.latest_version"
                      class="release-selected"
                      >最新版本</span
                    ><time>{{ formatDate(version.created_at) }}</time>
                  </header>
                  <p>
                    {{ version.release_notes || '此版本没有附加更新说明。' }}
                  </p>
                  <div class="release-bottom">
                    <span
                      >{{ formatBytes(version.package_size)
                      }}<template v-if="version.min_mofox_version">
                        · MoFox ≥ {{ version.min_mofox_version }}</template
                      ></span
                    ><a
                      class="btn btn-sm"
                      :href="api.skills.downloadUrl(skillId, version.version)"
                      @click="recordDownload"
                      ><AppIcon name="download" :size="14" /> 获取此版本</a
                    >
                  </div>
                </article></CatalogState
              >
            </section>
            <section
              v-show="tab === 'comments'"
              id="comments"
              class="catalog-panel dossier-chapter discussion-panel"
            >
              <div class="catalog-kicker">
                第四章　讨论 · {{ skill.comments_count }} 条
              </div>
              <h2 class="section-offset">交流使用体验</h2>
              <form
                v-if="auth.isAuthenticated"
                class="skill-comment-form"
                @submit.prevent="postComment"
              >
                <textarea
                  v-model="comment"
                  aria-label="评论内容"
                  placeholder="分享你的使用体验…"
                  maxlength="2000"
                  rows="4"
                  :disabled="commentBusy"
                ></textarea>
                <div>
                  <span>{{ comment.length }} / 2000</span
                  ><button
                    class="btn btn-primary btn-sm"
                    :disabled="commentBusy || !comment.trim()"
                  >
                    {{ commentBusy ? '发布中…' : '发布评论' }}
                  </button>
                </div>
              </form>
              <div v-else class="catalog-empty-note">
                {{
                  auth.loading ? '正在确认登录状态…' : '登录后可以发表评论。'
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
                ><CatalogComment
                  v-for="item in comments.data"
                  :key="item.id"
                  :comment="item"
                  :removable="canRemove(item)"
                  :deleting="deleting === item.id"
                  @remove="removeComment(item.id)"
              /></CatalogState>
            </section>
          </div>
          <aside class="catalog-aside">
            <section class="catalog-panel acquisition">
              <div class="acquisition-label">
                <span>获取技能</span><small>安装与兼容</small>
              </div>
              <h2 class="section-offset">
                {{
                  skill.latest_version
                    ? `v${skill.latest_version}`
                    : '暂无可获取版本'
                }}
              </h2>
              <p class="catalog-muted">下载技能包，按说明加入你的 MoFox。</p>
              <div class="catalog-actions">
                <a
                  v-if="downloadUrl"
                  class="btn btn-primary"
                  :href="downloadUrl"
                  @click="recordDownload"
                  ><AppIcon name="download" :size="16" /> 下载技能包</a
                ><button v-else class="btn btn-primary" disabled>
                  等待作者发布</button
                ><button
                  class="btn"
                  :disabled="likeBusy || auth.loading"
                  @click="toggleLike"
                >
                  {{
                    likeBusy
                      ? '更新中…'
                      : skill.viewer_has_liked
                        ? '已点赞 ✓'
                        : '喜欢这个技能 ＋'
                  }}
                </button>
              </div>
              <div class="catalog-stat-row">
                <div>
                  <b>{{ formatNumber(skill.download_count) }}</b
                  ><span>累计下载</span>
                </div>
                <div>
                  <b>{{ formatNumber(skill.likes_count) }}</b
                  ><span>喜欢</span>
                </div>
                <div>
                  <b>{{
                    skill.rating_count
                      ? Number(skill.rating_avg).toFixed(1)
                      : '—'
                  }}</b
                  ><span>{{ skill.rating_count }} 条评分</span>
                </div>
              </div>
              <dl class="catalog-facts">
                <div>
                  <dt>宿主版本</dt>
                  <dd>
                    {{
                      latestVersion?.min_mofox_version
                        ? `MoFox ≥ ${latestVersion.min_mofox_version}`
                        : '兼容性待确认'
                    }}
                  </dd>
                </div>
                <div>
                  <dt>安装包大小</dt>
                  <dd>
                    {{
                      latestVersion
                        ? formatBytes(latestVersion.package_size)
                        : '—'
                    }}
                  </dd>
                </div>
                <div>
                  <dt>最近发布</dt>
                  <dd>
                    {{
                      latestVersion ? formatDate(latestVersion.created_at) : '—'
                    }}
                  </dd>
                </div>
              </dl>
              <p v-if="versions.error" class="catalog-muted">
                版本信息未加载，<button
                  class="catalog-link"
                  @click="loadVersions"
                >
                  重试
                </button>
              </p>
            </section>
            <section class="catalog-panel community-rating">

              <h2 class="section-offset">社区评分</h2>
              <CatalogState
                :loading="rating.loading"
                :error="rating.error"
                :count="1"
                @retry="loadRating"
                ><div
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
                    v-for="score in 5"
                    :key="score"
                    :class="{
                      active: (rating.data.viewer_rating || 0) >= score,
                    }"
                    :aria-label="`评 ${score} 星`"
                    :aria-pressed="rating.data.viewer_rating === score"
                    :disabled="ratingBusy || auth.loading"
                    @click="rate(score)"
                  >
                    ★</button
                  ><button
                    v-if="rating.data.viewer_rating"
                    class="clear-rating"
                    :disabled="ratingBusy"
                    @click="rate(null)"
                  >
                    清除
                  </button>
                </div>
                <p class="catalog-caption">
                  {{
                    rating.data.viewer_rating
                      ? `我的评分：${rating.data.viewer_rating} 星`
                      : '点击星星，为技能评分'
                  }}
                </p></CatalogState
              ><a
                v-if="!auth.isAuthenticated && !auth.loading"
                class="login-link"
                :href="auth.getLoginUrl()"
                >GitHub 登录后参与互动 ↗</a
              >
            </section>
          </aside>
        </div>
        <div v-if="downloadUrl" class="mobile-acquire">
          <span
            >{{ skill.display_name
            }}<small>v{{ skill.latest_version }}</small></span
          ><a
            class="btn btn-primary"
            :href="downloadUrl"
            @click="recordDownload"
            ><AppIcon name="download" :size="16" /> 下载技能包</a
          >
        </div>
      </template></CatalogState
    >
  </CatalogFrame>
</template>
<style scoped>
.section-offset {
  margin-top: 18px !important;
}
.skill-document {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: 14px/1.9 var(--font-sans);
  color: var(--ink-700);
}
.skill-release {
  padding: 24px 0;
  border-bottom: 1px solid var(--line);
}
.skill-release:last-child {
  border: 0;
  padding-bottom: 0;
}
.skill-release header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
.skill-release header strong {
  font: 20px var(--font-mono);
  color: var(--blue-700);
}
.skill-release time {
  font: 11px var(--font-mono);
  color: var(--ink-500);
}
.skill-release p {
  font-size: 13px;
  color: var(--ink-700);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.release-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 11px;
  color: var(--ink-500);
}
.skill-comment-form {
  display: grid;
  gap: 12px;
  margin-bottom: 20px;
}
.skill-comment-form textarea {
  width: 100%;
  resize: vertical;
  border: 1px solid var(--line);
  border-radius: 3px;
  background: var(--surface-soft);
  padding: 14px;
  font-size: 14px;
  line-height: 1.75;
}
.skill-comment-form > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
.skill-comment-form span {
  font: 11px var(--font-mono);
  color: var(--ink-500);
}
.catalog-stars .clear-rating {
  font-size: 11px;
  padding: 6px;
  margin-left: 5px;
}
.login-link {
  display: block;
  margin-top: 17px;
  font-size: 11px;
  color: var(--blue-600);
}
</style>
