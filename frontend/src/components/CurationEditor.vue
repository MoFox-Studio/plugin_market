<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import api from '@/api'
import { useCurationStore } from '@/stores/curation'
import { useToastStore } from '@/stores/toast'
import type { Audience, CurationEntry, CurationEntryCreate, CurationEntryUpdate, SlotType, TargetType } from '@/types'
import { formatDate } from '@/utils/format'

const curation = useCurationStore()
const toast = useToastStore()

const loading = ref(false)
const saving = ref(false)

const slotOptions: Array<{ label: string; value: SlotType }> = [
  { label: '精选插件', value: 'featured_plugin' },
  { label: '精选作者', value: 'featured_author' },
  { label: '签名作品', value: 'signature_plugin' },
  { label: 'Hero', value: 'hero' },
  { label: 'Sidebar', value: 'sidebar' },
]

const targetOptions: Array<{ label: string; value: TargetType }> = [
  { label: '插件', value: 'plugin' },
  { label: '作者', value: 'author' },
]

const audienceOptions: Array<{ label: string; value: Audience }> = [
  { label: '所有人', value: 'all' },
  { label: '已登录用户', value: 'logged_in' },
  { label: '匿名用户', value: 'anonymous' },
  { label: '管理员', value: 'admins' },
  { label: '有作品作者', value: 'authors_with_plugin' },
]

const groupedEntries = computed(() => {
  const groups: Array<{ key: string; title: string; items: CurationEntry[] }> = [
    { key: 'plugin', title: 'Plugin 条目', items: [] },
    { key: 'author-signature', title: 'Author + Signature 条目', items: [] },
    { key: 'hero', title: 'Hero 条目', items: [] },
  ]
  for (const entry of curation.items) {
    if (entry.slot_type === 'hero') {
      groups[2].items.push(entry)
    } else if (entry.target_type === 'author' || entry.signature_plugin_id) {
      groups[1].items.push(entry)
    } else {
      groups[0].items.push(entry)
    }
  }
  return groups.filter((group) => group.items.length)
})

const draftMeta = computed({
  get() {
    return JSON.stringify(curation.draft?.display_meta || {}, null, 2)
  },
  set(value: string) {
    try {
      curation.updateDraft({ display_meta: value.trim() ? JSON.parse(value) : {} })
    } catch {
      // keep user text local until it becomes valid JSON
    }
  },
})

function toDatetimeLocal(value?: string | null): string {
  if (!value) {
    return ''
  }
  return value.slice(0, 16)
}

async function loadEntries(): Promise<void> {
  loading.value = true
  try {
    const result = await api.admin.curation.list()
    curation.setItems(result.items || [])
  } catch (error) {
    toast.show((error as Error).message || '加载运营条目失败', 'error')
  } finally {
    loading.value = false
  }
}

async function saveDraft(): Promise<void> {
  if (!curation.draft) {
    return
  }
  saving.value = true
  try {
    if (curation.editingId === null) {
      await api.admin.curation.create(curation.draft as CurationEntryCreate)
      toast.show('已创建运营条目', 'ok')
    } else {
      await api.admin.curation.update(curation.editingId, curation.draft as CurationEntryUpdate)
      toast.show('已更新运营条目', 'ok')
    }
    curation.cancelEdit()
    await loadEntries()
  } catch (error) {
    toast.show((error as Error).message || '保存运营条目失败', 'error')
  } finally {
    saving.value = false
  }
}

async function disableEntry(entryId: number): Promise<void> {
  try {
    await api.admin.curation.disable(entryId)
    toast.show('已停用运营条目', 'ok')
    await loadEntries()
  } catch (error) {
    toast.show((error as Error).message || '停用失败', 'error')
  }
}

async function moveEntry(entry: CurationEntry, direction: -1 | 1): Promise<void> {
  const ordered = [...curation.items].sort((left, right) => left.sort_order - right.sort_order)
  const index = ordered.findIndex((item) => item.id === entry.id)
  const nextIndex = index + direction
  if (index < 0 || nextIndex < 0 || nextIndex >= ordered.length) {
    return
  }
  const [moved] = ordered.splice(index, 1)
  ordered.splice(nextIndex, 0, moved)
  const ids = ordered.map((item) => item.id)
  curation.setPendingOrder(ids)
  try {
    const updated = await api.admin.curation.reorder(ids)
    curation.setItems(updated)
    curation.resetPendingOrder()
  } catch (error) {
    toast.show((error as Error).message || '排序失败', 'error')
  }
}

onMounted(() => {
  void loadEntries()
})
</script>

<template>
  <section class="curation-editor panel">
    <div class="section-head compact-head">
      <div>
        <h2>Curation Editor</h2>
        <p>集中管理 plugin / author+signature / hero 条目。</p>
      </div>
      <button class="btn btn-primary btn-sm" type="button" @click="curation.startCreate()">新建条目</button>
    </div>

    <div v-if="curation.draft" class="curation-editor-form">
      <label>
        <span>Slot</span>
        <select :value="curation.draft.slot_type" @change="curation.updateDraft({ slot_type: ($event.target as HTMLSelectElement).value as SlotType })">
          <option v-for="option in slotOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </label>
      <label>
        <span>Target</span>
        <select :value="curation.draft.target_type" @change="curation.updateDraft({ target_type: ($event.target as HTMLSelectElement).value as TargetType })">
          <option v-for="option in targetOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </label>
      <label>
        <span>Target ID</span>
        <input :value="curation.draft.target_id || ''" type="text" @input="curation.updateDraft({ target_id: ($event.target as HTMLInputElement).value })">
      </label>
      <label>
        <span>Signature Plugin</span>
        <input :value="curation.draft.signature_plugin_id || ''" type="text" placeholder="仅作者条目可选" @input="curation.updateDraft({ signature_plugin_id: ($event.target as HTMLInputElement).value || null })">
      </label>
      <label>
        <span>开始时间</span>
        <input :value="toDatetimeLocal(curation.draft.starts_at)" type="datetime-local" @input="curation.updateDraft({ starts_at: ($event.target as HTMLInputElement).value || null })">
      </label>
      <label>
        <span>结束时间</span>
        <input :value="toDatetimeLocal(curation.draft.ends_at)" type="datetime-local" @input="curation.updateDraft({ ends_at: ($event.target as HTMLInputElement).value || null })">
      </label>
      <label>
        <span>Audience</span>
        <select :value="curation.draft.audience || 'all'" @change="curation.updateDraft({ audience: ($event.target as HTMLSelectElement).value as Audience })">
          <option v-for="option in audienceOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </label>
      <label class="curation-editor-toggle">
        <input :checked="Boolean(curation.draft.enabled)" type="checkbox" @change="curation.updateDraft({ enabled: ($event.target as HTMLInputElement).checked })">
        <span>启用条目</span>
      </label>
      <label class="curation-editor-meta">
        <span>Display Meta (JSON)</span>
        <textarea v-model="draftMeta" rows="5"></textarea>
      </label>
      <div class="curation-editor-form-actions">
        <button class="btn btn-primary btn-sm" type="button" :disabled="saving" @click="saveDraft">保存</button>
        <button class="btn btn-ghost btn-sm" type="button" @click="curation.cancelEdit()">取消</button>
      </div>
    </div>

    <div v-if="loading" class="inbox-list-state">加载运营条目中…</div>
    <div v-else class="curation-editor-groups">
      <section v-for="group in groupedEntries" :key="group.key" class="curation-editor-group">
        <div class="section-head compact-head">
          <div><h3>{{ group.title }}</h3><p>{{ group.items.length }} 条</p></div>
        </div>
        <article v-for="entry in group.items" :key="entry.id" class="curation-editor-item">
          <div>
            <strong>{{ entry.target_id }}</strong>
            <p>
              {{ entry.slot_type }} / {{ entry.target_type }} / audience={{ entry.audience }}
              <span v-if="entry.signature_plugin_id"> / signature={{ entry.signature_plugin_id }}</span>
            </p>
            <small>
              sort={{ entry.sort_order }} · {{ entry.enabled ? 'enabled' : 'disabled' }} ·
              {{ entry.starts_at ? formatDate(entry.starts_at) : '立即生效' }}
            </small>
          </div>
          <div class="curation-editor-actions">
            <button class="btn btn-ghost btn-sm" type="button" @click="moveEntry(entry, -1)">上移</button>
            <button class="btn btn-ghost btn-sm" type="button" @click="moveEntry(entry, 1)">下移</button>
            <button class="btn btn-sm" type="button" @click="curation.startEdit(entry)">编辑</button>
            <button class="btn btn-sm" type="button" @click="disableEntry(entry.id)">停用</button>
          </div>
        </article>
      </section>
      <div v-if="!groupedEntries.length" class="profile-editor-preview profile-editor-preview-surface">
        <strong>还没有运营条目。</strong>
      </div>
    </div>
  </section>
</template>