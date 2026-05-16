<script setup lang="ts">
import { onMounted, ref } from 'vue'
import api from '@/api'
import { useAnnouncementsStore } from '@/stores/announcements'
import { useToastStore } from '@/stores/toast'
import { formatDate, formatRelative } from '@/utils/format'
import type { Announcement, Audience, DisplayMode, Severity } from '@/types'

interface AnnouncementDraft {
  title: string
  body_markdown: string
  display_mode: DisplayMode
  severity: Severity
  dismissible: boolean
  enabled: boolean
  starts_at: string | null
  ends_at: string | null
  audience: Audience
  emit_inbox: boolean
}

const toast = useToastStore()
const announcements = useAnnouncementsStore()

const loading = ref(true)
const saving = ref(false)
const items = ref<Announcement[]>([])
const editingId = ref<number | null>(null)
const draft = ref<AnnouncementDraft>(createDraft())

const audienceOptions: Audience[] = ['all', 'logged_in', 'anonymous', 'admins', 'authors_with_plugin']
const severityOptions: Severity[] = ['info', 'warning', 'critical']
const modeOptions: DisplayMode[] = ['banner', 'modal']

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
  }
}

function toDatetimeLocal(value?: string | null): string {
  return value ? value.slice(0, 16) : ''
}

function startCreate(): void {
  editingId.value = null
  draft.value = createDraft()
}

function startEdit(item: Announcement): void {
  editingId.value = item.id
  draft.value = {
    title: item.title,
    body_markdown: item.body_markdown,
    display_mode: item.display_mode,
    severity: item.severity,
    dismissible: item.dismissible,
    enabled: item.enabled,
    starts_at: item.starts_at || null,
    ends_at: item.ends_at || null,
    audience: item.audience,
    emit_inbox: item.emit_inbox,
  }
}

async function loadAnnouncements(): Promise<void> {
  loading.value = true
  try {
    const result = await api.admin.announcements.list({ limit: 100 })
    items.value = result.items || []
  } catch (error) {
    toast.show((error as Error).message || '加载公告失败', 'error')
  } finally {
    loading.value = false
  }
}

async function saveDraft(): Promise<void> {
  if (!draft.value.title.trim()) {
    toast.show('标题不能为空', 'error')
    return
  }
  saving.value = true
  try {
    const payload = {
      ...draft.value,
      title: draft.value.title.trim(),
      body_markdown: draft.value.body_markdown.trim(),
      starts_at: draft.value.starts_at || null,
      ends_at: draft.value.ends_at || null,
    }
    if (editingId.value === null) {
      await api.admin.announcements.create(payload)
      toast.show('公告已创建', 'ok')
    } else {
      await api.admin.announcements.update(editingId.value, payload)
      toast.show('公告已更新', 'ok')
    }
    startCreate()
    await announcements.loadActive(true)
    await loadAnnouncements()
  } catch (error) {
    toast.show((error as Error).message || '保存公告失败', 'error')
  } finally {
    saving.value = false
  }
}

async function disableAnnouncement(id: number): Promise<void> {
  try {
    await api.admin.announcements.disable(id)
    toast.show('公告已停用', 'ok')
    await announcements.loadActive(true)
    await loadAnnouncements()
  } catch (error) {
    toast.show((error as Error).message || '停用失败', 'error')
  }
}

async function resurfaceAnnouncement(id: number): Promise<void> {
  try {
    await api.admin.announcements.resurface(id)
    toast.show('公告已重新上线', 'ok')
    await announcements.loadActive(true)
    await loadAnnouncements()
  } catch (error) {
    toast.show((error as Error).message || '重新上线失败', 'error')
  }
}

onMounted(() => {
  void loadAnnouncements()
})
</script>

<template>
  <section class="admin-subview-stack">
    <section class="panel curation-editor-form admin-form-grid">
      <div class="section-head compact-head admin-form-head">
        <div>
          <h2>公告管理</h2>
          <p>创建、编辑、停用和重新上线系统公告。</p>
        </div>
        <button class="btn btn-ghost btn-sm" type="button" @click="startCreate">新建草稿</button>
      </div>

      <label>
        <span>标题</span>
        <input :value="draft.title" type="text" maxlength="120" @input="draft.title = ($event.target as HTMLInputElement).value">
      </label>
      <label>
        <span>展示方式</span>
        <select :value="draft.display_mode" @change="draft.display_mode = ($event.target as HTMLSelectElement).value as DisplayMode">
          <option v-for="item in modeOptions" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <label>
        <span>严重级别</span>
        <select :value="draft.severity" @change="draft.severity = ($event.target as HTMLSelectElement).value as Severity">
          <option v-for="item in severityOptions" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <label>
        <span>Audience</span>
        <select :value="draft.audience" @change="draft.audience = ($event.target as HTMLSelectElement).value as Audience">
          <option v-for="item in audienceOptions" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <label>
        <span>开始时间</span>
        <input :value="toDatetimeLocal(draft.starts_at)" type="datetime-local" @input="draft.starts_at = ($event.target as HTMLInputElement).value || null">
      </label>
      <label>
        <span>结束时间</span>
        <input :value="toDatetimeLocal(draft.ends_at)" type="datetime-local" @input="draft.ends_at = ($event.target as HTMLInputElement).value || null">
      </label>
      <label class="curation-editor-toggle">
        <input :checked="draft.dismissible" type="checkbox" @change="draft.dismissible = ($event.target as HTMLInputElement).checked">
        <span>允许 dismiss</span>
      </label>
      <label class="curation-editor-toggle">
        <input :checked="draft.emit_inbox" type="checkbox" @change="draft.emit_inbox = ($event.target as HTMLInputElement).checked">
        <span>同步发到信箱</span>
      </label>
      <label class="curation-editor-toggle">
        <input :checked="draft.enabled" type="checkbox" @change="draft.enabled = ($event.target as HTMLInputElement).checked">
        <span>启用公告</span>
      </label>
      <label class="curation-editor-meta">
        <span>正文</span>
        <textarea :value="draft.body_markdown" rows="6" @input="draft.body_markdown = ($event.target as HTMLTextAreaElement).value"></textarea>
      </label>
      <div class="curation-editor-form-actions">
        <button class="btn btn-primary btn-sm" type="button" :disabled="saving" @click="saveDraft">保存公告</button>
      </div>
    </section>

    <section class="panel">
      <div class="section-head compact-head">
        <div>
          <h2>公告列表</h2>
          <p>当前按更新时间展示最近 100 条公告。</p>
        </div>
      </div>
      <div v-if="loading" class="inbox-list-state">加载公告中…</div>
      <div v-else class="admin-card-list">
        <article v-for="item in items" :key="item.id" class="curation-editor-item">
          <div>
            <strong>{{ item.title }}</strong>
            <p>{{ item.display_mode }} / {{ item.severity }} / audience={{ item.audience }}</p>
            <small>
              {{ item.enabled ? 'enabled' : 'disabled' }} · {{ formatDate(item.created_at) }} · 更新于 {{ formatRelative(item.updated_at) }}
            </small>
          </div>
          <div class="curation-editor-actions">
            <button class="btn btn-sm" type="button" @click="startEdit(item)">编辑</button>
            <button v-if="item.enabled" class="btn btn-sm" type="button" @click="disableAnnouncement(item.id)">停用</button>
            <button v-else class="btn btn-sm" type="button" @click="resurfaceAnnouncement(item.id)">重新上线</button>
          </div>
        </article>
      </div>
    </section>
  </section>
</template>