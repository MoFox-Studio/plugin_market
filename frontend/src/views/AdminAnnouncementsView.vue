<script setup lang="ts">
import MarketSelect from '@/components/MarketSelect.vue';
import MarketDateTime from '@/components/MarketDateTime.vue';
import { onMounted, onBeforeUnmount, ref } from 'vue';
import PageSkeleton from '@/components/PageSkeleton.vue';
import EmptyState from '@/components/EmptyState.vue';
import api from '@/api';
import { useAnnouncementsStore } from '@/stores/announcements';
import { useToastStore } from '@/stores/toast';
import {
  datetimeLocalToIso,
  formatDate,
  formatRelative,
  toDatetimeLocalValue,
} from '@/utils/format';
import type { Announcement, Audience, DisplayMode, Severity } from '@/types';

interface AnnouncementDraft {
  title: string;
  body_markdown: string;
  display_mode: DisplayMode;
  severity: Severity;
  dismissible: boolean;
  enabled: boolean;
  starts_at: string | null;
  ends_at: string | null;
  audience: Audience;
  emit_inbox: boolean;
}

const toast = useToastStore();
const announcements = useAnnouncementsStore();

const loading = ref(true);
const error = ref('');
const actionPending = ref(false);
let requestId = 0;
let disposed = false;
const labels: Record<string, string> = {
  all: '所有人',
  logged_in: '已登录用户',
  anonymous: '访客',
  admins: '管理员',
  authors_with_plugin: '插件作者',
  info: '通知',
  warning: '提醒',
  critical: '重要',
  banner: '横幅',
  modal: '弹窗',
};
const saving = ref(false);
const items = ref<Announcement[]>([]);
const editingId = ref<number | null>(null);
const draft = ref<AnnouncementDraft>(createDraft());

const audienceOptions: Audience[] = [
  'all',
  'logged_in',
  'anonymous',
  'admins',
  'authors_with_plugin',
];
const severityOptions: Severity[] = ['info', 'warning', 'critical'];
const modeOptions: DisplayMode[] = ['banner', 'modal'];

function createDraft(): AnnouncementDraft {
  return {
    title: '',
    body_markdown: '',
    display_mode: 'banner',
    severity: 'info',
    dismissible: true,
    enabled: true,
    starts_at: null,
    ends_at: null,
    audience: 'all',
    emit_inbox: false,
  };
}

function startCreate(): void {
  editingId.value = null;
  draft.value = createDraft();
}

function startEdit(item: Announcement): void {
  if (saving.value || actionPending.value) return;
  editingId.value = item.id;
  draft.value = {
    title: item.title,
    body_markdown: item.body_markdown,
    display_mode: item.display_mode,
    severity: item.severity,
    dismissible: item.dismissible,
    enabled: item.enabled,
    starts_at: toDatetimeLocalValue(item.starts_at) || null,
    ends_at: toDatetimeLocalValue(item.ends_at) || null,
    audience: item.audience,
    emit_inbox: item.emit_inbox,
  };
}

async function loadAnnouncements(): Promise<void> {
  if (disposed) return;
  const request = ++requestId;
  loading.value = true;
  error.value = '';
  try {
    const result = await api.admin.announcements.list({ limit: 100 });
    if (request === requestId && !disposed) items.value = result.items || [];
  } catch (e) {
    if (request === requestId && !disposed)
      error.value = (e as Error).message || '加载公告失败';
  } finally {
    if (request === requestId && !disposed) loading.value = false;
  }
}

async function saveDraft(): Promise<void> {
  if (saving.value || actionPending.value || disposed) return;
  if (!draft.value.title.trim()) {
    toast.show('标题不能为空', 'warning');
    return;
  }
  if (
    draft.value.starts_at &&
    draft.value.ends_at &&
    new Date(draft.value.ends_at) <= new Date(draft.value.starts_at)
  ) {
    toast.show('结束时间必须晚于开始时间', 'warning');
    return;
  }
  saving.value = true;
  try {
    const payload = {
      ...draft.value,
      title: draft.value.title.trim(),
      body_markdown: draft.value.body_markdown.trim(),
      starts_at: datetimeLocalToIso(draft.value.starts_at),
      ends_at: datetimeLocalToIso(draft.value.ends_at),
    };
    if (editingId.value === null) {
      await api.admin.announcements.create(payload);
      toast.show('公告已创建', 'ok');
    } else {
      await api.admin.announcements.update(editingId.value, payload);
      toast.show('公告已更新', 'ok');
    }
    if (disposed) return;
    startCreate();
    await announcements.loadActive(true);
    await loadAnnouncements();
  } catch (error) {
    toast.show((error as Error).message || '保存公告失败', 'error');
  } finally {
    saving.value = false;
  }
}

async function disableAnnouncement(id: number): Promise<void> {
  if (saving.value || actionPending.value || disposed) return;
  actionPending.value = true;
  try {
    await api.admin.announcements.disable(id);
    if (disposed) return;
    toast.show('公告已停用', 'ok');
    await announcements.loadActive(true);
    await loadAnnouncements();
  } catch (error) {
    if (!disposed) toast.show((error as Error).message || '停用失败', 'error');
  } finally {
    actionPending.value = false;
  }
}

async function resurfaceAnnouncement(id: number): Promise<void> {
  if (saving.value || actionPending.value || disposed) return;
  actionPending.value = true;
  try {
    await api.admin.announcements.resurface(id);
    if (disposed) return;
    toast.show('公告已重新上线', 'ok');
    await announcements.loadActive(true);
    await loadAnnouncements();
  } catch (error) {
    if (!disposed)
      toast.show((error as Error).message || '重新上线失败', 'error');
  } finally {
    actionPending.value = false;
  }
}

onMounted(() => {
  void loadAnnouncements();
});
onBeforeUnmount(() => {
  disposed = true;
  requestId++;
});
</script>

<template>
  <section class="admin-subview-stack">
    <fieldset
      :disabled="saving || actionPending"
      class="panel curation-editor-form admin-form-grid"
    >
      <div class="section-head compact-head admin-form-head">
        <div>
          <h1 class="desk-title">{{ editingId === null ? '新建公告' : '编辑公告 #' + editingId }}</h1>
          <p>撰写市场公告，并设置展示对象、发布时段和通知方式。</p>
        </div>
        <button class="btn btn-ghost btn-sm" type="button" @click="startCreate">
          新建草稿
        </button>
      </div>

      <label class="form-wide">
        <span>标题</span>
        <input
          :value="draft.title"
          type="text"
          maxlength="120"
          @input="draft.title = ($event.target as HTMLInputElement).value"
        />
      </label>
      <label class="curation-editor-meta">
        <span>正文</span>
        <textarea
          :value="draft.body_markdown"
          rows="6"
          @input="
            draft.body_markdown = ($event.target as HTMLTextAreaElement).value
          "
        ></textarea>
      </label>
      <h2 class="form-chapter">发布设置</h2>
      <label>
        <span>展示方式</span>
        <MarketSelect
          :value="draft.display_mode"
          @change="
            draft.display_mode = ($event.target as HTMLSelectElement)
              .value as DisplayMode
          "
        >
          <option v-for="item in modeOptions" :key="item" :value="item">
            {{ labels[item] || item }}
          </option>
        </MarketSelect>
      </label>
      <label>
        <span>严重级别</span>
        <MarketSelect
          :value="draft.severity"
          @change="
            draft.severity = ($event.target as HTMLSelectElement)
              .value as Severity
          "
        >
          <option v-for="item in severityOptions" :key="item" :value="item">
            {{ labels[item] || item }}
          </option>
        </MarketSelect>
      </label>
      <label>
        <span>展示人群</span>
        <MarketSelect
          :value="draft.audience"
          @change="
            draft.audience = ($event.target as HTMLSelectElement)
              .value as Audience
          "
        >
          <option v-for="item in audienceOptions" :key="item" :value="item">
            {{ labels[item] || item }}
          </option>
        </MarketSelect>
      </label>
      <label>
        <span>开始时间</span>
        <MarketDateTime
          :value="toDatetimeLocalValue(draft.starts_at)"
          type="datetime-local"
          @input="
            draft.starts_at = ($event.target as HTMLInputElement).value || null
          "
        />
      </label>
      <label>
        <span>结束时间</span>
        <MarketDateTime
          :value="toDatetimeLocalValue(draft.ends_at)"
          type="datetime-local"
          @input="
            draft.ends_at = ($event.target as HTMLInputElement).value || null
          "
        />
      </label>
      <label class="curation-editor-toggle">
        <input
          :checked="draft.dismissible"
          type="checkbox"
          @change="
            draft.dismissible = ($event.target as HTMLInputElement).checked
          "
        />
        <span>允许用户关闭</span>
      </label>
      <label class="curation-editor-toggle">
        <input
          :checked="draft.emit_inbox"
          type="checkbox"
          @change="
            draft.emit_inbox = ($event.target as HTMLInputElement).checked
          "
        />
        <span>同步发到信箱</span>
      </label>
      <label class="curation-editor-toggle">
        <input
          :checked="draft.enabled"
          type="checkbox"
          @change="draft.enabled = ($event.target as HTMLInputElement).checked"
        />
        <span>启用公告</span>
      </label>
      <div class="curation-editor-form-actions">
        <button
          class="btn btn-primary btn-sm"
          type="button"
          :disabled="saving"
          @click="saveDraft"
        >
          {{ saving ? '保存中…' : '保存公告' }}
        </button>
      </div>
    </fieldset>

    <section class="panel">
      <div class="section-head compact-head">
        <div>
          <h2>已存公告</h2>
          <p>当前按更新时间展示最近 100 条公告。</p>
        </div>
      </div>
      <PageSkeleton v-if="loading" type="rows" :count="4" />
      <div v-else-if="error" class="admin-error" role="alert">
        <p>{{ error }}</p>
        <button class="btn" @click="loadAnnouncements">重新加载</button>
      </div>
      <EmptyState
        v-else-if="!items.length"
        title="暂无公告"
        message="创建第一条公告，向市场用户传达消息。"
      />
      <div v-else class="admin-card-list">
        <article
          v-for="item in items"
          :key="item.id"
          class="curation-editor-item"
        >
          <div>
            <strong>{{ item.title }}</strong>
            <p>
              {{ labels[item.display_mode] }} / {{ labels[item.severity] }} /
              {{ labels[item.audience] }}
            </p>
            <small>
              {{ item.enabled ? '已启用' : '已停用' }} ·
              {{ formatDate(item.created_at) }} · 更新于
              {{ formatRelative(item.updated_at) }}
            </small>
          </div>
          <div class="curation-editor-actions">
            <button
              class="btn btn-sm"
              type="button"
              :disabled="saving || actionPending"
              @click="startEdit(item)"
            >
              编辑
            </button>
            <button
              v-if="item.enabled"
              class="btn btn-sm"
              type="button"
              :disabled="saving || actionPending"
              @click="disableAnnouncement(item.id)"
            >
              停用
            </button>
            <button
              v-else
              class="btn btn-sm"
              type="button"
              :disabled="saving || actionPending"
              @click="resurfaceAnnouncement(item.id)"
            >
              重新上线
            </button>
          </div>
        </article>
      </div>
    </section>
  </section>
</template>
<style scoped>
fieldset {
  min-width: 0;
  margin: 0;
}
fieldset:disabled {
  opacity: 0.7;
}
.curation-editor-meta,
.curation-editor-form-actions {
  grid-column: 1/-1;
}
</style>
