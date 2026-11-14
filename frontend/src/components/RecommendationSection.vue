<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRecommendationsStore } from '@/stores/recommendations';
import { useAuthStore } from '@/stores/auth';
import { categoryLabel, formatNumber } from '@/utils/format';
import type {
  RecommendationFeedback,
  RecommendationItem,
} from '@/types/recommendations';
import RecommendationPreferences from './RecommendationPreferences.vue';
import PageSkeleton from './PageSkeleton.vue';
import AppIcon from './AppIcon.vue';
const props = withDefaults(
  defineProps<{ placement?: 'home' | 'detail'; contextPluginId?: string }>(),
  { placement: 'home' },
);
const store = useRecommendationsStore(),
  auth = useAuthStore();
const preferencesOpen = ref(false),
  feedbackError = ref('');
const undo = ref<RecommendationFeedback | null>(null);
let identityVersion = 0;
watch(
  () => auth.viewer?.author_id,
  () => {
    identityVersion++;
    undo.value = null;
    feedbackError.value = '';
    preferencesOpen.value = false;
  },
  { flush: 'sync' },
);
const context = computed(() => ({
  placement: props.placement,
  context_plugin_id: props.contextPluginId,
}));
const batch = computed(() => store.state(context.value));
const subtitle = computed(() => {
  const hasInterests =
    store.preferences.personalization_enabled &&
    (store.preferences.interests.categories.length ||
      store.preferences.interests.tags.length);
  if (batch.value.data?.mode === 'personalized')
    return '根据你的兴趣、订阅与关注';
  if (hasInterests) return '根据你选择的兴趣';
  return batch.value.data?.mode === 'contextual'
    ? '与当前插件用途相关'
    : '先看看热门与新上架';
});
watch(
  [
    () => props.placement,
    () => props.contextPluginId,
    () => auth.loaded,
    () => auth.viewer?.author_id,
    () => store.revision,
  ],
  () => void store.load(context.value),
  { immediate: true },
);
async function feedback(
  item: RecommendationItem,
  type: 'not_interested' | 'already_have' | 'reduce_category',
) {
  feedbackError.value = '';
  const id = identityVersion;
  const f: RecommendationFeedback =
    type === 'reduce_category'
      ? { type, category: item.plugin.categories?.[0] }
      : { type, plugin_id: item.plugin.plugin_id };
  try {
    const saved = await store.update({ feedback: f });
    if (saved && id === identityVersion) undo.value = f;
  } catch (err) {
    if (id === identityVersion)
      feedbackError.value = err instanceof Error ? err.message : '反馈保存失败';
  }
}
async function undoFeedback() {
  if (!undo.value) return;
  const f = undo.value,
    id = identityVersion;
  try {
    const saved = await store.update({
      feedback:
        f.type === 'reduce_category'
          ? { type: 'restore_category', category: f.category }
          : { type: 'restore_plugin', plugin_id: f.plugin_id },
    });
    if (saved && id === identityVersion) undo.value = null;
  } catch (err) {
    if (id === identityVersion)
      feedbackError.value = err instanceof Error ? err.message : '撤销失败';
  }
}
</script>
<template>
  <section
    class="recommendation-section"
    aria-labelledby="recommendation-heading"
    :aria-busy="batch.loading"
  >
    <header class="recommendation-head">
      <div>
        <h2 id="recommendation-heading">
          {{ placement === 'home' ? '猜你喜欢' : '你可能还喜欢' }}
        </h2>
        <p>{{ subtitle }}</p>
      </div>
      <div class="recommendation-controls">
        <button
          :disabled="batch.loading || !batch.data?.next_cursor"
          @click="store.load(context, { next: true })"
        >
          换一批 ↻</button
        ><button @click="preferencesOpen = true">
          管理推荐 <span>↗</span>
        </button>
      </div>
    </header>
    <div v-if="undo" class="recommendation-feedback" role="status">
      已更新推荐偏好。<button :disabled="store.saving" @click="undoFeedback">
        撤销
      </button>
    </div>
    <p v-if="feedbackError" class="recommendation-error" role="alert">
      {{ feedbackError }}
    </p>
    <PageSkeleton v-if="batch.loading && !batch.data" :count="6" />
    <div v-else-if="batch.error" class="recommendation-state" role="status">
      <h3>推荐暂时不可用</h3>
      <p>{{ batch.error }}</p>
      <button class="btn" @click="store.load(context, { force: true })">
        重新加载 ↗
      </button>
    </div>
    <div v-else-if="!batch.data?.items.length" class="recommendation-state">
      <span class="eyebrow">MORE POSSIBILITIES AHEAD</span>
      <h3>暂时没有更多合适的插件</h3>
      <p>调整兴趣或恢复忽略项，继续发现社区作品。</p>
      <button class="btn" @click="preferencesOpen = true">调整推荐偏好</button
      ><router-link to="/browse" class="recommendation-browse"
        >浏览全部插件 ↗</router-link
      >
    </div>
    <div
      v-else
      class="recommendation-grid"
      :class="{ 'is-refreshing': batch.loading }"
    >
      <article
        v-for="(item, i) in batch.data.items"
        :key="item.plugin.plugin_id"
        class="recommendation-card"
      >
        <div class="recommendation-card__top">
          <span>{{
            categoryLabel(item.plugin.categories?.[0] || 'other')
          }}</span>
          <details>
            <summary :aria-label="item.plugin.display_name + '的推荐选项'">
              •••
            </summary>
            <div class="recommendation-menu">
              <button
                :disabled="store.saving"
                @click="feedback(item, 'not_interested')"
              >
                不感兴趣</button
              ><button
                :disabled="store.saving"
                @click="feedback(item, 'already_have')"
              >
                我已有这个</button
              ><button
                v-if="item.plugin.categories?.length"
                :disabled="store.saving"
                @click="feedback(item, 'reduce_category')"
              >
                减少此分类
              </button>
            </div>
          </details>
        </div>
        <router-link
          :to="{
            name: 'plugin',
            params: { id: item.plugin.plugin_id },
            query: { version: item.recommended_version },
          }"
          class="recommendation-card__link"
        >
          <div class="recommendation-identity">
            <img
              v-if="item.plugin.icon_url"
              :src="item.plugin.icon_url"
              alt=""
              loading="lazy"
            /><span v-else class="recommendation-initial">{{
              item.plugin.display_name.slice(0, 1)
            }}</span>
            <div>
              <h3>{{ item.plugin.display_name }}</h3>
              <p>
                {{
                  item.plugin.owner_display_name ||
                  item.plugin.owner_login ||
                  item.plugin.owner_id
                }}
              </p>
            </div>
          </div>
          <p class="recommendation-summary">{{ item.plugin.summary }}</p>
          <div class="recommendation-reasons">
            <span
              v-for="reason in item.reasons.slice(0, 2)"
              :key="reason.code"
              >{{ reason.label }}</span
            >
          </div>
          <div class="recommendation-meta">
            <span v-market-tooltip="'下载次数'"
              ><AppIcon name="download" :size="13" />{{
                formatNumber(item.plugin.downloads_count)
              }}</span
            ><span>{{
              item.plugin.rating_count
                ? '★ ' + item.plugin.rating_avg.toFixed(1)
                : '暂无评分'
            }}</span
            ><span class="recommendation-number"
              >{{ String(i + 1).padStart(2, '0') }} ↗</span
            >
          </div>
        </router-link>
        <div class="recommendation-compatibility">
          <span>v{{ item.recommended_version }}</span
          ><span>{{
            item.compatibility === 'compatible'
              ? '与你的环境兼容'
              : '兼容性待确认'
          }}</span>
        </div>
      </article>
    </div>
    <p
      v-if="batch.data?.items.length && batch.exhausted"
      class="recommendation-end"
    >
      本轮合适的推荐已展示完毕。也可以<a href="/browse">浏览全部插件 ↗</a>
    </p>
    <RecommendationPreferences
      :open="preferencesOpen"
      @close="preferencesOpen = false"
    />
  </section>
</template>
<style scoped>
.recommendation-section {
  margin: 64px 0;
  min-width: 0;
}
.recommendation-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}
.recommendation-head h2 {
  font-size: clamp(30px, 3vw, 45px);
  letter-spacing: -0.04em;
  line-height: 1.3;
  margin: 10px 0 0;
}
.recommendation-head p {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--ink-500);
}
.recommendation-controls {
  display: flex;
  gap: 20px;
  white-space: nowrap;
  font-size: 12px;
}
.recommendation-controls button:disabled {
  opacity: 0.35;
}
.recommendation-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  transition: opacity 150ms;
}
.is-refreshing {
  opacity: 0.55;
  pointer-events: none;
}
.recommendation-card {
  border: 1px solid var(--line);
  background: var(--surface);
  min-width: 0;
  position: relative;
  transition: border-color 180ms;
}
.recommendation-card:hover {
  border-color: var(--blue-500);
}
.recommendation-card__top {
  padding: 16px 20px 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-size: 9px;
  color: var(--ink-500);
  letter-spacing: 0.04em;
}
.recommendation-card__top details {
  position: relative;
}
.recommendation-card__top summary {
  list-style: none;
  cursor: pointer;
  padding: 4px 0 4px 12px;
  font-size: 12px;
  letter-spacing: 2px;
}
.recommendation-card__top summary::-webkit-details-marker {
  display: none;
}
.recommendation-menu {
  position: absolute;
  right: 0;
  top: 100%;
  z-index: 5;
  width: 150px;
  display: grid;
  background: var(--surface-elevated);
  box-shadow: var(--shadow-2);
  border: 1px solid var(--line);
  padding: 6px;
}
.recommendation-menu button {
  padding: 10px;
  font-size: 12px;
  text-align: left;
  letter-spacing: 0;
  color: var(--ink-900);
}
.recommendation-menu button:hover {
  background: var(--surface-soft);
}
.recommendation-card__link {
  display: block;
  padding: 16px 20px 20px;
}
.recommendation-identity {
  display: flex;
  gap: 12px;
  align-items: center;
}
.recommendation-identity img,
.recommendation-initial {
  width: 42px;
  height: 42px;
  object-fit: contain;
  background: var(--surface-soft);
  border: 1px solid var(--line);
  flex-shrink: 0;
}
.recommendation-initial {
  display: grid;
  place-items: center;
  font-size: 20px;
  color: var(--blue-700);
}
.recommendation-identity > div {
  min-width: 0;
}
.recommendation-identity h3 {
  font-size: 15px;
  line-height: 1.4;
  letter-spacing: -0.02em;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.recommendation-identity p {
  font-size: 10px;
  color: var(--ink-500);
  margin: 4px 0 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.recommendation-summary {
  color: var(--ink-500);
  font-size: 12px;
  line-height: 1.8;
  margin: 18px 0;
  min-height: 44px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.recommendation-reasons {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
  min-height: 20px;
  margin-bottom: 20px;
}
.recommendation-reasons span {
  font-size: 9px;
  background: var(--blue-50);
  color: var(--blue-700);
  padding: 3px 6px;
}
.recommendation-meta {
  display: flex;
  gap: 16px;
  font: 10px var(--font-mono);
  color: var(--ink-500);
}
.recommendation-meta > span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.recommendation-number {
  margin-left: auto;
  color: var(--blue-700);
}
.recommendation-compatibility {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 20px;
  border-top: 1px solid var(--line-soft);
  font: 9px var(--font-mono);
  color: var(--ink-500);
}
.recommendation-state {
  text-align: center;
  padding: 48px 24px;
  border: 1px solid var(--line);
  background: var(--surface);
}
.recommendation-state h3 {
  font-size: 20px;
  margin: 14px 0;
}
.recommendation-state p {
  font-size: 13px;
  color: var(--ink-500);
  margin: 0 0 24px;
}
.recommendation-browse {
  display: inline-block;
  margin: 0 20px;
  font-size: 12px;
}
.recommendation-error {
  color: var(--danger-ink);
  font-size: 12px;
}
.recommendation-feedback {
  padding: 12px 16px;
  background: var(--blue-50);
  border-left: 2px solid var(--blue-500);
  font-size: 12px;
  margin-bottom: 16px;
  display: flex;
  gap: 16px;
}
.recommendation-feedback button {
  color: var(--blue-700);
  text-decoration: underline;
}
.recommendation-end {
  font-size: 10px;
  color: var(--ink-500);
  margin: 16px 0 0;
}
.recommendation-end a {
  margin-left: 8px;
  color: var(--blue-700);
}
@media (max-width: 1100px) {
  .recommendation-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 600px) {
  .recommendation-grid {
    grid-template-columns: 1fr;
  }
  .recommendation-head {
    align-items: flex-start;
    flex-direction: column;
    gap: 16px;
  }
  .recommendation-head h2 {
    font-size: 25px;
  }
  .recommendation-section {
    margin: 48px 0;
  }
  .recommendation-card__link {
    padding: 16px 20px;
  }
  .recommendation-summary {
    min-height: 0;
  }
  .recommendation-controls {
    align-self: flex-end;
  }
  .recommendation-identity h3 {
    font-size: 16px;
  }
}
</style>
