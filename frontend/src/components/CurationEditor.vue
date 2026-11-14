<script setup lang="ts">
import MarketSelect from '@/components/MarketSelect.vue';
import MarketDateTime from '@/components/MarketDateTime.vue';
import { computed, onMounted, onBeforeUnmount, ref } from 'vue';
import PageSkeleton from '@/components/PageSkeleton.vue';
import EmptyState from '@/components/EmptyState.vue';
import api from '@/api';
import { useCurationStore } from '@/stores/curation';
import { useToastStore } from '@/stores/toast';
import type {
  Audience,
  CurationEntry,
  CurationEntryCreate,
  CurationEntryUpdate,
  SlotType,
  TargetType,
} from '@/types';
import {
  formatDate,
  datetimeLocalToIso,
  toDatetimeLocalValue,
} from '@/utils/format';

const curation = useCurationStore();
const toast = useToastStore();

const loading = ref(false);
const saving = ref(false);
const error = ref('');
const actionPending = ref(false);
const draftMeta = ref('{}');
let requestId = 0;
let disposed = false;

const slotOptions: Array<{ label: string; value: SlotType }> = [
  { label: '精选插件', value: 'featured_plugin' },
  { label: '精选作者', value: 'featured_author' },
  { label: '签名作品', value: 'signature_plugin' },
  { label: '首页主视觉', value: 'hero' },
  { label: '侧栏推荐', value: 'sidebar' },
];

const targetOptions: Array<{ label: string; value: TargetType }> = [
  { label: '插件', value: 'plugin' },
  { label: '作者', value: 'author' },
];

const audienceOptions: Array<{ label: string; value: Audience }> = [
  { label: '所有人', value: 'all' },
  { label: '已登录用户', value: 'logged_in' },
  { label: '匿名用户', value: 'anonymous' },
  { label: '管理员', value: 'admins' },
  { label: '有作品作者', value: 'authors_with_plugin' },
];

const groupedEntries = computed(() => {
  const groups: Array<{ key: string; title: string; items: CurationEntry[] }> =
    [
      { key: 'plugin', title: '插件推荐', items: [] },
      { key: 'author-signature', title: '作者与代表作', items: [] },
      { key: 'hero', title: '首页主视觉', items: [] },
    ];
  for (const entry of curation.items) {
    if (entry.slot_type === 'hero') {
      groups[2].items.push(entry);
    } else if (entry.target_type === 'author' || entry.signature_plugin_id) {
      groups[1].items.push(entry);
    } else {
      groups[0].items.push(entry);
    }
  }
  return groups.filter((group) => group.items.length);
});

const metaError = computed(() => {
  try {
    const parsed = JSON.parse(draftMeta.value || '{}');
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? ''
      : '展示配置必须是 JSON 对象。';
  } catch {
    return 'JSON 格式尚未完成，修正后即可保存。';
  }
});
function startCreate(): void {
  if (saving.value || actionPending.value) return;
  curation.startCreate();
  draftMeta.value = '{}';
}
function startEdit(entry: CurationEntry): void {
  if (saving.value || actionPending.value) return;
  curation.startEdit(entry);
  curation.updateDraft({
    starts_at: toDatetimeLocalValue(entry.starts_at) || null,
    ends_at: toDatetimeLocalValue(entry.ends_at) || null,
  });
  draftMeta.value = JSON.stringify(entry.display_meta || {}, null, 2);
}
async function loadEntries(): Promise<void> {
  if (disposed) return;
  const request = ++requestId;
  loading.value = true;
  error.value = '';
  try {
    const result = await api.admin.curation.list();
    if (request === requestId && !disposed)
      curation.setItems(result.items || []);
  } catch (e) {
    if (request === requestId && !disposed)
      error.value = (e as Error).message || '加载运营条目失败';
  } finally {
    if (request === requestId && !disposed) loading.value = false;
  }
}
async function saveDraft(): Promise<void> {
  if (!curation.draft || saving.value || actionPending.value || disposed)
    return;
  if (metaError.value) {
    toast.show(metaError.value, 'error');
    return;
  }
  if (!curation.draft.target_id?.trim()) {
    toast.show('请填写目标 ID', 'error');
    return;
  }
  const payload = {
    ...curation.draft,
    target_id: curation.draft.target_id.trim(),
    display_meta: JSON.parse(draftMeta.value || '{}'),
    starts_at: datetimeLocalToIso(curation.draft.starts_at),
    ends_at: datetimeLocalToIso(curation.draft.ends_at),
  };
  if (
    payload.starts_at &&
    payload.ends_at &&
    new Date(payload.ends_at) <= new Date(payload.starts_at)
  ) {
    toast.show('结束时间必须晚于开始时间', 'error');
    return;
  }
  saving.value = true;
  try {
    if (curation.editingId === null)
      await api.admin.curation.create(payload as CurationEntryCreate);
    else
      await api.admin.curation.update(
        curation.editingId,
        payload as CurationEntryUpdate,
      );
    if (disposed) return;
    toast.show('运营条目已保存', 'ok');
    curation.cancelEdit();
    await loadEntries();
  } catch (e) {
    if (!disposed)
      toast.show((e as Error).message || '保存运营条目失败', 'error');
  } finally {
    saving.value = false;
  }
}
async function disableEntry(entryId: number): Promise<void> {
  if (saving.value || actionPending.value || disposed) return;
  actionPending.value = true;
  try {
    await api.admin.curation.disable(entryId);
    if (disposed) return;
    toast.show('已停用运营条目', 'ok');
    await loadEntries();
  } catch (e) {
    if (!disposed) toast.show((e as Error).message || '停用失败', 'error');
  } finally {
    actionPending.value = false;
  }
}
async function moveEntry(
  entry: CurationEntry,
  direction: -1 | 1,
): Promise<void> {
  if (saving.value || actionPending.value || disposed) return;
  const ordered = [...curation.items].sort(
    (left, right) => left.sort_order - right.sort_order,
  );
  const index = ordered.findIndex((item) => item.id === entry.id);
  const nextIndex = index + direction;
  if (index < 0 || nextIndex < 0 || nextIndex >= ordered.length) return;
  const [moved] = ordered.splice(index, 1);
  ordered.splice(nextIndex, 0, moved);
  const ids = ordered.map((item) => item.id);
  actionPending.value = true;
  curation.setPendingOrder(ids);
  try {
    const updated = await api.admin.curation.reorder(ids);
    if (!disposed) curation.setItems(updated);
  } catch (e) {
    if (!disposed) toast.show((e as Error).message || '排序失败', 'error');
  } finally {
    if (!disposed) curation.resetPendingOrder();
    actionPending.value = false;
  }
}
onMounted(() => {
  curation.cancelEdit();
  curation.setItems([]);
  curation.resetPendingOrder();
  void loadEntries();
});
onBeforeUnmount(() => {
  disposed = true;
  requestId++;
  curation.cancelEdit();
  curation.setItems([]);
  curation.resetPendingOrder();
});
</script>

<template>
  <section class="curation-editor panel">
    <div class="section-head compact-head">
      <div>
        <h1 class="desk-title">首页策展</h1>
        <p>编排精选插件、作者代表作与首页展示内容。</p>
      </div>
      <button
        class="btn btn-primary btn-sm"
        type="button"
        :disabled="saving || actionPending"
        @click="startCreate"
      >
        新建条目
      </button>
    </div>

    <fieldset
      v-if="curation.draft"
      :disabled="saving || actionPending"
      class="curation-editor-form"
    >
      <legend>编排条目</legend>
      <h2 class="form-chapter">内容与刊位</h2>
      <label>
        <span>展示位置</span>
        <MarketSelect
          :value="curation.draft.slot_type"
          @change="
            curation.updateDraft({
              slot_type: ($event.target as HTMLSelectElement).value as SlotType,
            })
          "
        >
          <option
            v-for="option in slotOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </MarketSelect>
      </label>
      <label>
        <span>内容类型</span>
        <MarketSelect
          :value="curation.draft.target_type"
          @change="
            curation.updateDraft({
              target_type: ($event.target as HTMLSelectElement)
                .value as TargetType,
            })
          "
        >
          <option
            v-for="option in targetOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </MarketSelect>
      </label>
      <label>
        <span>目标 ID</span>
        <input
          :value="curation.draft.target_id || ''"
          type="text"
          @input="
            curation.updateDraft({
              target_id: ($event.target as HTMLInputElement).value,
            })
          "
        />
      </label>
      <label>
        <span>作者代表作 ID</span>
        <input
          :value="curation.draft.signature_plugin_id || ''"
          type="text"
          placeholder="仅作者条目可选"
          @input="
            curation.updateDraft({
              signature_plugin_id:
                ($event.target as HTMLInputElement).value || null,
            })
          "
        />
      </label>
      <h2 class="form-chapter">时段与受众</h2>
      <label>
        <span>开始时间</span>
        <MarketDateTime
          :value="toDatetimeLocalValue(curation.draft.starts_at)"
          type="datetime-local"
          @input="
            curation.updateDraft({
              starts_at: ($event.target as HTMLInputElement).value || null,
            })
          "
        />
      </label>
      <label>
        <span>结束时间</span>
        <MarketDateTime
          :value="toDatetimeLocalValue(curation.draft.ends_at)"
          type="datetime-local"
          @input="
            curation.updateDraft({
              ends_at: ($event.target as HTMLInputElement).value || null,
            })
          "
        />
      </label>
      <label>
        <span>展示人群</span>
        <MarketSelect
          :value="curation.draft.audience || 'all'"
          @change="
            curation.updateDraft({
              audience: ($event.target as HTMLSelectElement).value as Audience,
            })
          "
        >
          <option
            v-for="option in audienceOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </MarketSelect>
      </label>
      <label class="curation-editor-toggle">
        <input
          :checked="Boolean(curation.draft.enabled)"
          type="checkbox"
          @change="
            curation.updateDraft({
              enabled: ($event.target as HTMLInputElement).checked,
            })
          "
        />
        <span>启用条目</span>
      </label>
      <label class="curation-editor-meta">
        <span>展示配置 · JSON</span>
        <textarea
          v-model="draftMeta"
          rows="5"
          spellcheck="false"
          :aria-invalid="!!metaError"
        ></textarea
        ><small v-if="metaError" class="curation-error">{{ metaError }}</small>
      </label>
      <div class="curation-editor-form-actions">
        <button
          class="btn btn-primary btn-sm"
          type="button"
          :disabled="saving || !!metaError"
          @click="saveDraft"
        >
          {{ saving ? '保存中…' : '保存' }}
        </button>
        <button
          class="btn btn-ghost btn-sm"
          type="button"
          @click="curation.cancelEdit()"
        >
          取消
        </button>
      </div>
    </fieldset>

    <PageSkeleton v-if="loading" type="rows" :count="4" />
    <div v-else-if="error" class="admin-error" role="alert">
      <p>{{ error }}</p>
      <button class="btn" @click="loadEntries">重新加载</button>
    </div>
    <div v-else class="curation-editor-groups">
      <section
        v-for="group in groupedEntries"
        :key="group.key"
        class="curation-editor-group"
      >
        <div class="section-head compact-head">
          <div>
            <h2>{{ group.title }}</h2>
            <p>{{ group.items.length }} 条</p>
          </div>
        </div>
        <article
          v-for="entry in group.items"
          :key="entry.id"
          class="curation-editor-item"
        >
          <div>
            <strong>{{ entry.target_id }}</strong>
            <p>
              {{ targetOptions.find(option => option.value === entry.target_type)?.label || entry.target_type }}
              · {{ audienceOptions.find(option => option.value === entry.audience)?.label || entry.audience }}
              <span v-if="entry.signature_plugin_id">
                · 代表作 {{ entry.signature_plugin_id }}</span
              >
            </p>
            <small>
              排序 {{ entry.sort_order }} ·
              {{ entry.enabled ? '已启用' : '已停用' }} ·
              {{ entry.starts_at ? formatDate(entry.starts_at) : '立即生效' }}
            </small>
          </div>
          <div class="curation-editor-actions">
            <button
              class="btn btn-ghost btn-sm"
              type="button"
              :disabled="saving || actionPending"
              @click="moveEntry(entry, -1)"
            >
              上移
            </button>
            <button
              class="btn btn-ghost btn-sm"
              type="button"
              :disabled="saving || actionPending"
              @click="moveEntry(entry, 1)"
            >
              下移
            </button>
            <button
              class="btn btn-sm"
              type="button"
              :disabled="saving || actionPending"
              @click="startEdit(entry)"
            >
              编辑
            </button>
            <button
              class="btn btn-sm"
              type="button"
              :disabled="saving || actionPending || !entry.enabled"
              @click="disableEntry(entry.id)"
            >
              停用
            </button>
          </div>
        </article>
      </section>
      <EmptyState
        v-if="!groupedEntries.length"
        title="尚未添加推荐内容"
        message="新建条目，为首页编排精选内容。"
      />
    </div>
  </section>
</template>
<style scoped>
.curation-editor {
  display: grid;
  gap: 22px;
}
.curation-editor-form {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
  padding: 22px;
  background: var(--surface-soft);
  border: 1px solid var(--line);
  border-radius: 0;
  min-width: 0;
  margin: 0;
}
.curation-editor-form label {
  display: grid;
  gap: 8px;
  color: var(--ink-700);
  font-size: 12px;
}
.curation-editor-form input:not([type='checkbox']),
.curation-editor-form select,
.curation-editor-form textarea {
  width: 100%;
  min-width: 0;
  padding: 10px 12px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 3px;
  color: var(--ink-900);
  font: inherit;
}
.curation-editor-form textarea {
  font-family: var(--font-mono);
  resize: vertical;
}
.curation-editor-form .curation-editor-toggle {
  display: flex;
  align-items: center;
}
.curation-editor-meta,
.curation-editor-form-actions {
  grid-column: 1/-1;
}
.curation-editor-form-actions,
.curation-editor-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.curation-editor-groups {
  display: grid;
  gap: 28px;
}
.curation-editor-group h2 {
  font-size: 15px;
}
.curation-editor-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 18px 0;
  border-top: 1px solid var(--line);
}
.curation-editor-item strong {
  font-size: 13px;
  overflow-wrap: anywhere;
}
.curation-editor-item p,
.curation-editor-item small {
  font: 11px var(--font-mono);
  color: var(--ink-500);
  line-height: 1.8;
  overflow-wrap: anywhere;
}
.curation-error {
  color: var(--danger);
}
@media (max-width: 800px) {
  .curation-editor-form {
    grid-template-columns: 1fr 1fr;
  }
  .curation-editor-item {
    align-items: start;
    flex-direction: column;
    gap: 12px;
  }
}
@media (max-width: 500px) {
  .curation-editor-form {
    grid-template-columns: 1fr;
    padding: 16px;
  }
}
</style>
