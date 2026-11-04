import { defineStore } from 'pinia';
import { computed, onScopeDispose, reactive, ref, watch } from 'vue';
import api, { ApiError } from '@/api';
import { useAuthStore } from './auth';
import type {
  RecommendationPreferences,
  RecommendationFeedback,
  RecommendationContext,
  RecommendationResponse,
} from '@/types/recommendations';
const localKey = 'mofox:recommendations:v1';
function defaults(): RecommendationPreferences {
  return {
    personalization_enabled: false,
    interests: { categories: [], tags: [] },
    ignored_plugins: [],
    reduced_categories: [],
    revision: 0,
    updated_at: null,
    feedback_retention_days: 30,
  };
}
function loadLocal(): RecommendationPreferences {
  try {
    const parsed = JSON.parse(localStorage.getItem(localKey) || 'null');
    if (!parsed || typeof parsed !== 'object') return defaults();
    const now = Date.now(),
      base = defaults();
    base.personalization_enabled = parsed.personalization_enabled === true;
    const strings = (v: unknown, max: number) =>
      Array.isArray(v)
        ? v
            .filter((x): x is string => typeof x === 'string' && x.length <= 40)
            .slice(0, max)
        : [];
    if (Date.parse(parsed.interest_expires_at) > now) {
      base.interests = {
        categories: strings(parsed.interests?.categories, 3),
        tags: strings(parsed.interests?.tags, 10),
      };
    }
    base.ignored_plugins = Array.isArray(parsed.ignored_plugins)
      ? parsed.ignored_plugins
          .filter(
            (x: any) =>
              typeof x?.plugin_id === 'string' &&
              x.plugin_id.length <= 200 &&
              ['not_interested', 'already_have'].includes(x.reason) &&
              Date.parse(x.expires_at) > now,
          )
          .slice(0, 100)
      : [];
    base.reduced_categories = Array.isArray(parsed.reduced_categories)
      ? parsed.reduced_categories
          .filter(
            (x: any) =>
              typeof x?.category === 'string' && Date.parse(x.expires_at) > now,
          )
          .slice(0, 50)
      : [];
    return base;
  } catch {
    return defaults();
  }
}
interface Batch {
  data: RecommendationResponse | null;
  loading: boolean;
  error: string;
  seen: string[];
  exhausted: boolean;
  updated: number;
}
export const useRecommendationsStore = defineStore('recommendations', () => {
  const auth = useAuthStore();
  const preferences = ref<RecommendationPreferences>(loadLocal());
  const preferenceError = ref('');
  const saving = ref(false);
  const revision = ref(0);
  const batches = reactive<Record<string, Batch>>({});
  const controllers = new Map<string, AbortController>();
  let epoch = 0,
    identityGeneration = 0,
    prefsIdentity: string | null = null,
    prefsPending: Promise<void> | null = null;
  const identity = computed(() => auth.viewer?.author_id || 'anonymous');
  function key(context: RecommendationContext) {
    return context.placement + ':' + (context.context_plugin_id || '');
  }
  function state(context: RecommendationContext) {
    const k = key(context);
    if (!batches[k])
      batches[k] = {
        data: null,
        loading: false,
        error: '',
        seen: [],
        exhausted: false,
        updated: 0,
      };
    return batches[k];
  }
  function invalidate() {
    epoch++;
    for (const controller of controllers.values()) controller.abort();
    controllers.clear();
    for (const k of Object.keys(batches)) delete batches[k];
    revision.value++;
  }
  function resetIdentity() {
    identityGeneration++;
    invalidate();
    prefsIdentity = null;
    prefsPending = null;
    preferenceError.value = '';
    saving.value = false;
    preferences.value =
      identity.value === 'anonymous' ? loadLocal() : defaults();
  }
  watch(identity, resetIdentity, { flush: 'sync' });
  function interactions() {
    invalidate();
    prefsIdentity = null;
    prefsPending = null;
  }
  window.addEventListener('market:interactions-changed', interactions);
  onScopeDispose(() => {
    window.removeEventListener('market:interactions-changed', interactions);
    for (const c of controllers.values()) c.abort();
  });
  async function loadPreferences(force = false) {
    if (!auth.loaded) await auth.loadViewer();
    if (auth.error) throw new Error('无法确认当前身份，请重试。');
    const id = identity.value;
    if (prefsIdentity === id && !force) return;
    if (prefsPending && !force) return prefsPending;
    const ownEpoch = epoch;
    prefsPending = (async () => {
      try {
        const result =
          id === 'anonymous'
            ? loadLocal()
            : await api.get<RecommendationPreferences>(
                '/api/v1/me/recommendation-preferences',
              );
        if (ownEpoch !== epoch || id !== identity.value) return;
        preferences.value = result;
        prefsIdentity = id;
        preferenceError.value = '';
      } catch (err) {
        if (ownEpoch === epoch)
          preferenceError.value =
            err instanceof Error ? err.message : '推荐偏好加载失败';
        throw err;
      } finally {
        if (ownEpoch === epoch) prefsPending = null;
      }
    })();
    return prefsPending;
  }
  async function load(
    context: RecommendationContext,
    options: { next?: boolean; force?: boolean } = {},
  ) {
    const batch = state(context);
    if (batch.loading) return;
    // Keep the user's batch on return; explicit feedback/identity/content
    // mutations invalidate it, and advancing always revalidates on the server.
    if (batch.data && !options.force && !options.next) return;
    if (options.next && !batch.data?.next_cursor) {
      batch.exhausted = true;
      return;
    }
    batch.loading = true;
    batch.error = '';
    const k = key(context),
      ownEpoch = epoch,
      controller = new AbortController();
    controllers.get(k)?.abort();
    controllers.set(k, controller);
    try {
      await loadPreferences();
      if (ownEpoch !== epoch) return;
      const prefs = preferences.value;
      const excluded = options.next
        ? [
            ...new Set([
              ...batch.seen,
              ...(batch.data?.items.map((x) => x.plugin.plugin_id) || []),
            ]),
          ].slice(-100)
        : [];
      const payload = {
        ...context,
        limit: 6,
        interests: prefs.personalization_enabled
          ? prefs.interests
          : { categories: [], tags: [] },
        reduced_categories: prefs.reduced_categories.map((x) => x.category),
        exclude_ids: [
          ...new Set([
            ...(identity.value === 'anonymous'
              ? prefs.ignored_plugins.map((x) => x.plugin_id)
              : []),
            ...excluded,
          ]),
        ].slice(0, 100),
        cursor: options.next ? batch.data?.next_cursor : undefined,
      };
      const response = await api.post<RecommendationResponse>(
        '/api/v1/recommendations',
        payload,
        { signal: controller.signal },
      );
      if (ownEpoch !== epoch || controller.signal.aborted) return;
      batch.data = response;
      batch.seen = excluded;
      batch.exhausted = !response.next_cursor;
      batch.updated = Date.now();
    } catch (err) {
      if (ownEpoch !== epoch || controller.signal.aborted) return;
      if (
        err instanceof ApiError &&
        err.code === 'STALE_RECOMMENDATION_CURSOR'
      ) {
        batch.data = null;
        batch.seen = [];
        batch.error = '推荐条件已更新，请重新加载。';
      } else
        batch.error = err instanceof Error ? err.message : '推荐暂时不可用';
    } finally {
      if (ownEpoch === epoch) {
        batch.loading = false;
        if (controllers.get(k) === controller) controllers.delete(k);
      }
    }
  }
  function persistLocal() {
    const value = preferences.value;
    try {
      localStorage.setItem(
        localKey,
        JSON.stringify({
          ...value,
          interest_expires_at: new Date(
            Date.now() + 30 * 86400000,
          ).toISOString(),
        }),
      );
    } catch {
      preferenceError.value =
        '浏览器未允许保存偏好，本次设置仅在当前页面有效。';
    }
  }
  async function update(
    payload: Partial<
      Pick<RecommendationPreferences, 'personalization_enabled' | 'interests'>
    > & { feedback?: RecommendationFeedback },
  ) {
    if (saving.value) return false;
    saving.value = true;
    preferenceError.value = '';
    const id = identity.value,
      ownIdentity = identityGeneration;
    try {
      if (
        payload.interests &&
        (payload.interests.categories.length > 3 ||
          payload.interests.tags.length > 10 ||
          [...payload.interests.categories, ...payload.interests.tags].some(
            (label) => !label.trim() || label.length > 40,
          ))
      ) {
        throw new Error('最多选择 3 个分类、10 个标签，每项不得超过 40 字。');
      }
      await loadPreferences();
      if (id !== identity.value || ownIdentity !== identityGeneration)
        return false;
      if (id !== 'anonymous') {
        const result = await api.put<RecommendationPreferences>(
          '/api/v1/me/recommendation-preferences',
          payload,
        );
        if (id !== identity.value || ownIdentity !== identityGeneration)
          return false;
        preferences.value = result;
      } else {
        const next: RecommendationPreferences = JSON.parse(
          JSON.stringify(preferences.value),
        );
        if (payload.personalization_enabled !== undefined)
          next.personalization_enabled = payload.personalization_enabled;
        if (payload.interests) next.interests = payload.interests;
        const f = payload.feedback,
          expires_at = new Date(Date.now() + 30 * 86400000).toISOString();
        if (f?.plugin_id) {
          next.ignored_plugins = next.ignored_plugins.filter(
            (x) => x.plugin_id !== f.plugin_id,
          );
          if (f.type === 'not_interested' || f.type === 'already_have') {
            if (next.ignored_plugins.length >= 100)
              throw new Error(
                '忽略列表已达到 100 项，请先在管理推荐中恢复一些条目。',
              );
            next.ignored_plugins.push({
              plugin_id: f.plugin_id,
              reason: f.type,
              expires_at,
            });
          }
        }
        if (f?.category) {
          next.reduced_categories = next.reduced_categories.filter(
            (x) => x.category !== f.category,
          );
          if (f.type === 'reduce_category')
            next.reduced_categories.push({ category: f.category, expires_at });
        }
        preferences.value = next;
        persistLocal();
      }
      invalidate();
      return true;
    } catch (err) {
      if (ownIdentity !== identityGeneration) return false;
      preferenceError.value =
        err instanceof Error ? err.message : '设置保存失败';
      throw err;
    } finally {
      if (ownIdentity === identityGeneration) saving.value = false;
    }
  }
  async function reset() {
    if (saving.value) return false;
    saving.value = true;
    preferenceError.value = '';
    const id = identity.value,
      ownIdentity = identityGeneration;
    try {
      const result =
        id === 'anonymous'
          ? defaults()
          : await api.del<RecommendationPreferences>(
              '/api/v1/me/recommendation-preferences',
            );
      if (id !== identity.value || ownIdentity !== identityGeneration)
        return false;
      preferences.value = result;
      if (id === 'anonymous')
        try {
          localStorage.removeItem(localKey);
        } catch {}
      invalidate();
      return true;
    } catch (err) {
      if (ownIdentity !== identityGeneration) return false;
      preferenceError.value = err instanceof Error ? err.message : '重置失败';
      throw err;
    } finally {
      if (ownIdentity === identityGeneration) saving.value = false;
    }
  }
  return {
    preferences,
    preferenceError,
    saving,
    revision,
    batches,
    state,
    key,
    load,
    loadPreferences,
    update,
    reset,
    invalidate,
  };
});
