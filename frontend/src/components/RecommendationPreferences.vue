<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRecommendationsStore } from '@/stores/recommendations';
import { useTaxonomyStore } from '@/stores/taxonomy';
import { useAuthStore } from '@/stores/auth';
import { categoryLabel } from '@/utils/format';
const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: [] }>();
const store = useRecommendationsStore(),
  taxonomy = useTaxonomyStore(),
  auth = useAuthStore();
const dialog = ref<HTMLDialogElement | null>(null);
const enabled = ref(false),
  categories = ref<string[]>([]),
  tags = ref('');
const feedbackError = ref('');
const refreshing = ref(false);
const ready = ref(false);
let previous: HTMLElement | null = null;
let identityVersion = 0;
let refreshVersion = 0;
watch(
  () => auth.viewer?.author_id,
  () => {
    identityVersion++;
    refreshVersion++;
    refreshing.value = false;
    ready.value = false;
    enabled.value = false;
    categories.value = [];
    tags.value = '';
    feedbackError.value = '';
    if (props.open) emit('close');
  },
  { flush: 'sync' },
);
const retained = computed(() => (auth.isAuthenticated ? 90 : 30));
async function refresh() {
  const id = ++refreshVersion;
  refreshing.value = true;
  ready.value = false;
  feedbackError.value = '';
  try {
    await Promise.all([store.loadPreferences(), taxonomy.load()]);
    if (id !== refreshVersion) return;
    enabled.value = store.preferences.personalization_enabled;
    categories.value = [...store.preferences.interests.categories];
    tags.value = store.preferences.interests.tags.join(', ');
    ready.value = true;
  } catch (err) {
    if (id === refreshVersion)
      feedbackError.value = err instanceof Error ? err.message : '偏好加载失败';
  } finally {
    if (id === refreshVersion) refreshing.value = false;
  }
}
watch(
  () => props.open,
  async (value) => {
    if (value) {
      previous = document.activeElement as HTMLElement;
      dialog.value?.showModal();
      await refresh();
    } else {
      dialog.value?.close();
      previous?.focus();
    }
  },
);
onMounted(() => {
  if (props.open) {
    dialog.value?.showModal();
    void refresh();
  }
});
async function save() {
  if (!ready.value || refreshing.value) return;
  feedbackError.value = '';
  const id = identityVersion;
  try {
    const saved = await store.update({
      personalization_enabled: enabled.value,
      interests: {
        categories: categories.value.slice(0, 3),
        tags: tags.value
          .split(/[,，]/)
          .map((t) => t.trim())
          .filter(Boolean),
      },
    });
    if (saved && id === identityVersion) emit('close');
  } catch (err) {
    if (id === identityVersion)
      feedbackError.value = err instanceof Error ? err.message : '保存失败';
  }
}
async function restore(pluginId: string) {
  const id = identityVersion;
  try {
    await store.update({
      feedback: { type: 'restore_plugin', plugin_id: pluginId },
    });
  } catch (err) {
    if (id === identityVersion)
      feedbackError.value = err instanceof Error ? err.message : '恢复失败';
  }
}
async function restoreCategory(category: string) {
  const id = identityVersion;
  try {
    await store.update({ feedback: { type: 'restore_category', category } });
  } catch (err) {
    if (id === identityVersion)
      feedbackError.value = err instanceof Error ? err.message : '恢复失败';
  }
}
async function reset() {
  const id = identityVersion;
  try {
    const saved = await store.reset();
    if (saved && id === identityVersion) await refresh();
  } catch (err) {
    if (id === identityVersion)
      feedbackError.value = err instanceof Error ? err.message : '重置失败';
  }
}
function toggle(category: string) {
  if (categories.value.includes(category))
    categories.value = categories.value.filter((x) => x !== category);
  else if (categories.value.length < 3) categories.value.push(category);
}
</script>
<template>
  <dialog
    ref="dialog"
    class="recommendation-dialog"
    aria-labelledby="recommendation-preferences-title"
    @cancel.prevent="emit('close')"
  >
    <header>
      <div>
        <span class="eyebrow">YOUR DISCOVERY / 你的发现</span>
        <h2 id="recommendation-preferences-title">让推荐更合心意</h2>
      </div>
      <button
        class="icon-button"
        aria-label="关闭推荐设置"
        @click="emit('close')"
      >
        ×
      </button>
    </header>
    <p class="preferences-intro">
      {{
        auth.isAuthenticated
          ? '开启后，结合你选择的兴趣、订阅、评分和关注作者推荐。'
          : '无需登录。选择感兴趣的方向，偏好仅保存在当前浏览器。'
      }}
    </p>
    <p v-if="refreshing" role="status">正在读取推荐偏好…</p>
    <fieldset
      class="preference-fields"
      :disabled="refreshing || !ready || store.saving"
    >
      <label class="personalization-toggle"
        ><input v-model="enabled" type="checkbox" /><span
          >启用个性化推荐<small>关闭后仍可发现热门与新发布作品</small></span
        ></label
      >
      <fieldset>
        <legend>
          感兴趣的分类
          <small>最多 3 个 · 已选 {{ categories.length }} 个</small>
        </legend>
        <div class="interest-options">
          <button
            v-for="category in taxonomy.categories"
            :key="category"
            type="button"
            :aria-pressed="categories.includes(category)"
            :disabled="!categories.includes(category) && categories.length >= 3"
            @click="toggle(category)"
          >
            {{ categoryLabel(category) }}
          </button>
        </div>
        <p v-if="!taxonomy.categories.length">
          分类暂不可用。<button
            class="text-button"
            @click="taxonomy.load(true)"
          >
            重试
          </button>
        </p>
      </fieldset>
      <label class="preference-tags"
        >兴趣标签 <span>可选，逗号分隔，最多 10 个</span
        ><input v-model="tags" maxlength="500" placeholder="例如：工具, 音乐"
      /></label>
    </fieldset>
    <section
      v-if="store.preferences.ignored_plugins.length"
      class="preferences-ignored"
    >
      <h3>已忽略的插件</h3>
      <div
        v-for="item in store.preferences.ignored_plugins"
        :key="item.plugin_id"
      >
        <span
          >{{ item.plugin_id
          }}<small>{{
            item.reason === 'already_have' ? '我已有这个' : '不感兴趣'
          }}</small></span
        ><button :disabled="store.saving" @click="restore(item.plugin_id)">
          恢复
        </button>
      </div>
    </section>
    <section
      v-if="store.preferences.reduced_categories.length"
      class="preferences-ignored"
    >
      <h3>减少推荐的分类</h3>
      <div
        v-for="item in store.preferences.reduced_categories"
        :key="item.category"
      >
        <span>{{ categoryLabel(item.category) }}</span
        ><button
          :disabled="store.saving"
          @click="restoreCategory(item.category)"
        >
          恢复
        </button>
      </div>
    </section>
    <p class="preferences-retention">
      不记录浏览历史。{{
        auth.isAuthenticated ? '推荐反馈' : '本机兴趣和反馈'
      }}
      {{ retained }} 天后过期；重置不会删除订阅、关注或评分。
    </p>
    <p
      v-if="feedbackError || store.preferenceError"
      class="preferences-error"
      role="alert"
    >
      {{ feedbackError || store.preferenceError }}
    </p>
    <button v-if="!ready && !refreshing" class="btn" @click="refresh">
      重试读取偏好
    </button>
    <footer>
      <button
        class="text-button"
        :disabled="store.saving || refreshing || !ready"
        @click="reset"
      >
        重置偏好</button
      ><button
        class="btn btn-primary"
        :disabled="store.saving || refreshing || !ready"
        @click="save"
      >
        {{ store.saving ? '正在保存…' : '保存设置 ↗' }}
      </button>
    </footer>
  </dialog>
</template>
<style scoped>
.recommendation-dialog {
  width: min(580px, calc(100vw - 32px));
  max-height: 88dvh;
  overflow: auto;
  border: 1px solid var(--line);
  border-top: 3px solid var(--blue-500);
  background: var(--paper);
  color: var(--ink-900);
  padding: 28px;
}
.recommendation-dialog::backdrop {
  background: var(--overlay-strong);
  backdrop-filter: blur(4px);
}
.recommendation-dialog header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
}
.recommendation-dialog h2 {
  font-size: 26px;
  margin: 10px 0 0;
}
.preferences-intro {
  font-size: 13px;
  line-height: 1.8;
  color: var(--ink-500);
  margin: 20px 0;
}
.personalization-toggle {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px;
  border: 1px solid var(--line);
  font-size: 13px;
}
.personalization-toggle input {
  accent-color: var(--blue-700);
  width: 17px;
  height: 17px;
}
.personalization-toggle small {
  display: block;
  color: var(--ink-500);
  font-size: 11px;
  margin-top: 4px;
}
fieldset {
  padding: 0;
  border: 0;
  margin: 24px 0;
}
legend {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 14px;
}
legend small {
  font-size: 11px;
  color: var(--ink-500);
  margin-left: 8px;
  font-weight: 400;
}
.interest-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.interest-options button {
  border: 1px solid var(--line);
  padding: 7px 12px;
  font-size: 12px;
  background: var(--surface);
}
.interest-options button[aria-pressed='true'] {
  border-color: var(--blue-600);
  color: var(--blue-700);
  background: var(--blue-50);
}
.interest-options button:disabled {
  opacity: 0.4;
}
.preference-tags {
  font-size: 13px;
  display: block;
}
.preference-tags span {
  font-size: 11px;
  color: var(--ink-500);
  margin-left: 8px;
}
.preference-tags input {
  margin-top: 10px;
  padding: 10px 12px;
  width: 100%;
  border: 1px solid var(--line);
  background: var(--surface);
  font-size: 14px;
}
.preferences-ignored {
  margin-top: 24px;
}
.preferences-ignored h3 {
  font-size: 13px;
}
.preferences-ignored > div {
  padding: 12px 0;
  border-bottom: 1px solid var(--line);
  display: flex;
  justify-content: space-between;
  gap: 16px;
  font-size: 12px;
}
.preferences-ignored span {
  overflow-wrap: anywhere;
}
.preferences-ignored small {
  color: var(--ink-500);
  display: block;
  margin-top: 4px;
}
.preferences-ignored button,
.text-button {
  color: var(--blue-700);
  font-size: 12px;
}
.preferences-retention {
  font-size: 11px;
  color: var(--ink-500);
  line-height: 1.8;
  margin: 24px 0;
}
.preferences-error {
  color: var(--danger-ink);
  font-size: 12px;
}
.recommendation-dialog footer {
  border-top: 1px solid var(--line);
  padding-top: 20px;
  display: flex;
  justify-content: space-between;
  gap: 16px;
}
@media (max-width: 600px) {
  .recommendation-dialog {
    padding: 22px;
  }
  .recommendation-dialog h2 {
    font-size: 23px;
  }
  .preference-tags input {
    font-size: 16px;
  }
}
</style>
