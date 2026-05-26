<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import api from '@/api'
import { useAdminStore } from '@/stores/admin'
import { useTaxonomyStore } from '@/stores/taxonomy'
import { useToastStore } from '@/stores/toast'
import { formatNumber, formatRelative, statusText, trustLevelLabel, categoryLabel } from '@/utils/format'
import type { BulkAction, Plugin, PluginSnapshot } from '@/types'
import DataTable from '@/components/DataTable.vue'
import BulkActionBar from '@/components/BulkActionBar.vue'
import EmptyState from '@/components/EmptyState.vue'
import TrustBadge from '@/components/TrustBadge.vue'

const admin = useAdminStore()
const taxonomy = useTaxonomyStore()
const toast = useToastStore()

const plugins = ref<Plugin[]>([])
const selectedId = ref<string | null>(null)
const selectedPlugin = ref<Plugin | null>(null)
const snapshot = ref<PluginSnapshot | null>(null)
const loading = ref(true)
const sortKey = ref('updated_at')
const sortDirection = ref<'asc' | 'desc'>('desc')

const tableColumns = [
  { key: 'display_name', label: '图标 + 名称', sortable: true, cell: (row: Record<string, unknown>) => `${String(row.icon_url ? '◉' : String(row.display_name || '?').slice(0, 1).toUpperCase())} ${String(row.display_name || '-')}` },
  { key: 'owner_display_name', label: 'Owner', sortable: true, cell: (row: Record<string, unknown>) => String(row.owner_display_name || row.owner_login || row.owner_id || '-') },
  { key: 'status', label: '状态', sortable: true, cell: (row: Record<string, unknown>) => statusText(String(row.status || '')) },
  { key: 'trust_level', label: 'Trust', sortable: true, cell: (row: Record<string, unknown>) => trustLevelLabel(String(row.trust_level || '')) },
  { key: 'latest_version', label: '最新版本', sortable: true, cell: (row: Record<string, unknown>) => String(row.latest_version || '-') },
  { key: 'likes_count', label: '订阅', sortable: true, align: 'right' as const, cell: (row: Record<string, unknown>) => formatNumber(Number(row.likes_count || 0)) },
  { key: 'downloads_count', label: '下载', sortable: true, align: 'right' as const, cell: (row: Record<string, unknown>) => formatNumber(Number(row.downloads_count || 0)) },
  { key: 'comments_count', label: '评论', sortable: true, align: 'right' as const, cell: (row: Record<string, unknown>) => formatNumber(Number(row.comments_count || 0)) },
  { key: 'updated_at', label: '最近治理时间', sortable: true, cell: (row: Record<string, unknown>) => formatRelative(String(row.updated_at || '')) },
]

const bulkActions: Array<{ key: BulkAction; label: string; variant?: 'default' | 'danger'; requireReason?: boolean }> = [
  { key: 'publish', label: '批量上架' },
  { key: 'reject', label: '批量退回' },
  { key: 'deprecate', label: '批量下架' },
  { key: 'block', label: '批量封禁', variant: 'danger' as const },
  { key: 'delete', label: '批量删除', variant: 'danger' as const, requireReason: true },
]

const filteredPlugins = computed(() => {
  const query = admin.filters.query.trim().toLowerCase()
  const status = admin.filters.status
  const trustLevel = admin.filters.trustLevel
  const owner = admin.filters.owner.trim().toLowerCase()
  const category = admin.filters.category
  const tag = admin.filters.tag.trim().toLowerCase()
  const pendingOnly = admin.filters.pendingOnly

  const next = plugins.value.filter((plugin) => {
    const matchesQuery = !query || [plugin.display_name, plugin.plugin_id, plugin.summary, plugin.owner_display_name, plugin.owner_login, plugin.owner_id].some((value) => String(value || '').toLowerCase().includes(query))
    const matchesStatus = !status || plugin.status === status
    const matchesTrust = !trustLevel || plugin.trust_level === trustLevel
    const ownerText = [plugin.owner_display_name, plugin.owner_login, plugin.owner_id].map((value) => String(value || '').toLowerCase())
    const matchesOwner = !owner || ownerText.some((value) => value.includes(owner))
    const matchesCategory = !category || (plugin.categories || []).includes(category)
    const matchesTag = !tag || (plugin.tags || []).some((item) => item.toLowerCase().includes(tag))
    const matchesPending = !pendingOnly || plugin.status === 'pending_review'
    return matchesQuery && matchesStatus && matchesTrust && matchesOwner && matchesCategory && matchesTag && matchesPending
  })

  const sorted = [...next].sort((left, right) => {
    const leftValue = String((left as unknown as Record<string, unknown>)[sortKey.value] || '')
    const rightValue = String((right as unknown as Record<string, unknown>)[sortKey.value] || '')
    const direction = sortDirection.value === 'asc' ? 1 : -1
    return leftValue.localeCompare(rightValue, 'zh-CN') * direction
  })

  return sorted
})

watch(() => filteredPlugins.value.length, (total) => {
  admin.setPagination({ total })
}, { immediate: true })

const pagedPlugins = computed(() => {
  const start = (admin.pagination.page - 1) * admin.pagination.pageSize
  return filteredPlugins.value.slice(start, start + admin.pagination.pageSize)
})

const pendingCount = computed(() => plugins.value.filter((plugin) => plugin.status === 'pending_review').length)

async function loadPlugins(): Promise<void> {
  loading.value = true
  const [pluginResult] = await Promise.all([
    api.get('/api/v1/admin/plugins'),
    taxonomy.load(),
  ])
  plugins.value = pluginResult.items || []
  admin.setPagination({ total: plugins.value.length })
  if (!selectedId.value && plugins.value.length) {
    selectedId.value = plugins.value.find((plugin) => plugin.status === 'pending_review')?.plugin_id || plugins.value[0].plugin_id
  }
  if (selectedId.value) {
    await loadSnapshot()
  }
  loading.value = false
}

async function loadSnapshot(): Promise<void> {
  if (!selectedId.value) {
    snapshot.value = null
    selectedPlugin.value = null
    return
  }
  const result = await api.get(`/api/v1/admin/plugins/${encodeURIComponent(selectedId.value)}`).catch(() => null)
  snapshot.value = result
  selectedPlugin.value = result?.plugin || null
}

async function selectPlugin(id: string): Promise<void> {
  selectedId.value = id
  await loadSnapshot()
}

async function pluginAction(action: string, pluginId: string): Promise<void> {
  if (!confirm(`确认执行 ${action} 操作：${pluginId} ？`)) return
  const reason = action === 'delete' ? '' : (prompt('可填写操作原因，留空也可以。', '') || '')
  try {
    if (action === 'delete') {
      await api.del(`/api/v1/admin/plugins/${encodeURIComponent(pluginId)}`)
      if (selectedId.value === pluginId) {
        selectedId.value = null
        snapshot.value = null
        selectedPlugin.value = null
      }
    } else {
      await api.post(`/api/v1/admin/plugins/${encodeURIComponent(pluginId)}/${action}`, reason.trim() ? { reason: reason.trim() } : {})
    }
    toast.show(action === 'delete' ? '插件已删除' : '治理动作已执行', 'ok')
    await loadPlugins()
  } catch (e) {
    toast.show((e as Error).message || '操作失败', 'error')
  }
}

async function setTrustLevel(pluginId: string, level: string): Promise<void> {
  if (selectedPlugin.value?.trust_level === level) return
  const reason = prompt(`可填写切换为"${trustLevelLabel(level)}"的原因，留空也可以。`, '') || ''
  try {
    await api.post(`/api/v1/admin/plugins/${encodeURIComponent(pluginId)}/trust-level/${encodeURIComponent(level)}`, reason.trim() ? { reason: reason.trim() } : {})
    toast.show('社区标识已更新', 'ok')
    await loadSnapshot()
  } catch (e) {
    toast.show((e as Error).message || '切换失败', 'error')
  }
}

function handleSort(payload: { key: string; direction: 'asc' | 'desc' }): void {
  sortKey.value = payload.key
  sortDirection.value = payload.direction
}

function handlePageChange(page: number): void {
  admin.setPagination({ page })
}

function handleFilter<K extends 'query' | 'status' | 'trustLevel' | 'owner' | 'category' | 'tag'>(key: K, value: string): void {
  admin.setFilter(key, value)
  admin.setPagination({ page: 1 })
}

function handlePendingToggle(nextValue: boolean): void {
  admin.setFilter('pendingOnly', nextValue)
  admin.setPagination({ page: 1 })
}

function toggleSelection(pluginId: string): void {
  admin.toggleSelection(pluginId)
}

function toggleAllSelection(pluginIds: string[]): void {
  admin.setSelection(pluginIds)
}

async function applyBulkAction(payload: { action: BulkAction; params: Record<string, unknown> }): Promise<void> {
  try {
    const result = await admin.applyBulk(payload.action, payload.params)
    const failures = result.results.filter((item) => !item.ok)
    if (failures.length) {
      toast.show(`批量操作完成，但有 ${failures.length} 项失败`, 'error')
    } else {
      toast.show('批量操作已完成', 'ok')
    }
    admin.clearSelection()
    await loadPlugins()
  } catch (error) {
    toast.show((error as Error).message || '批量操作失败', 'error')
  }
}

onMounted(() => {
  void loadPlugins()
})
</script>

<template>
  <div v-if="loading" class="loading-screen">加载中…</div>
  <div v-else class="admin-plugins-view">
    <section class="panel">
      <div class="section-head compact-head">
        <div>
          <h2>插件治理表</h2>
          <p>独立处理插件搜索、筛选、批量动作和单插件治理。</p>
        </div>
        <div class="table-actions">
          <span class="badge trust-community">共 {{ admin.pagination.total }} 项</span>
          <span class="badge status-pending_review">待审核 {{ pendingCount }}</span>
        </div>
      </div>

      <div class="queue-table-filters admin-plugins-filters">
        <input class="profile-editor-input" :value="admin.filters.query" type="search" placeholder="搜索插件 / 摘要 / 作者 / ID" @input="handleFilter('query', ($event.target as HTMLInputElement).value)">
        <select class="profile-editor-input" :value="admin.filters.status" @change="handleFilter('status', ($event.target as HTMLSelectElement).value)">
          <option value="">全部状态</option>
          <option value="published">已发布</option>
          <option value="pending_review">待审核</option>
          <option value="draft">草稿</option>
          <option value="deprecated">已下架</option>
          <option value="blocked">已封禁</option>
        </select>
        <select class="profile-editor-input" :value="admin.filters.trustLevel" @change="handleFilter('trustLevel', ($event.target as HTMLSelectElement).value)">
          <option value="">全部标识</option>
          <option value="official">官方</option>
          <option value="verified">认证</option>
          <option value="community">社区</option>
        </select>
        <input class="profile-editor-input" :value="admin.filters.owner" type="search" placeholder="按 owner / login / author_id 过滤" @input="handleFilter('owner', ($event.target as HTMLInputElement).value)">
        <select class="profile-editor-input" :value="admin.filters.category" @change="handleFilter('category', ($event.target as HTMLSelectElement).value)">
          <option value="">全部分类</option>
          <option v-for="item in taxonomy.categories" :key="item" :value="item">{{ categoryLabel(item) }}</option>
        </select>
        <input class="profile-editor-input" :value="admin.filters.tag" type="search" placeholder="按 tag 过滤" @input="handleFilter('tag', ($event.target as HTMLInputElement).value)">
        <label class="admin-filter-toggle">
          <input :checked="admin.filters.pendingOnly" type="checkbox" @change="handlePendingToggle(($event.target as HTMLInputElement).checked)">
          <span>只看待审核</span>
        </label>
      </div>

      <p class="soft-note">当前后台列表接口未提供单独的未读评论数字段，因此表格列先展示总评论量。</p>

      <DataTable
        :columns="tableColumns"
        :rows="pagedPlugins as unknown as Record<string, unknown>[]"
        row-key="plugin_id"
        :selected-ids="admin.selectedIds"
        :sort-key="sortKey"
        :sort-direction="sortDirection"
        :page="admin.pagination.page"
        :page-size="admin.pagination.pageSize"
        :total="admin.pagination.total"
        @toggle-row="toggleSelection"
        @toggle-all="toggleAllSelection"
        @sort="handleSort"
        @page-change="handlePageChange"
        @row-activate="selectPlugin(String($event.plugin_id || ''))"
      />
    </section>

    <section class="panel" v-if="selectedPlugin">
      <div class="section-head compact-head">
        <div>
          <h2>{{ selectedPlugin.display_name }}</h2>
          <p>{{ selectedPlugin.summary }}</p>
        </div>
        <div class="table-actions">
          <TrustBadge :level="selectedPlugin.trust_level" />
          <span :class="['badge', `status-${selectedPlugin.status}`]">{{ statusText(selectedPlugin.status) }}</span>
        </div>
      </div>

      <div class="plugin-sheet-grid">
        <div>
          <h4>快速治理</h4>
          <p class="soft-note">插件列表聚焦批量动作，这里保留单插件快速处理入口。</p>
          <div class="table-actions admin-action-cluster">
            <button v-if="selectedPlugin.status !== 'published'" class="btn btn-sm" @click="pluginAction('publish', selectedPlugin.plugin_id)">重新上架</button>
            <button v-if="selectedPlugin.status !== 'draft'" class="btn btn-sm" @click="pluginAction('reject', selectedPlugin.plugin_id)">退回</button>
            <button v-if="selectedPlugin.status !== 'deprecated'" class="btn btn-sm" @click="pluginAction('deprecate', selectedPlugin.plugin_id)">下架</button>
            <button v-if="selectedPlugin.status !== 'blocked'" class="btn btn-sm btn-danger" @click="pluginAction('block', selectedPlugin.plugin_id)">封禁</button>
            <button class="btn btn-sm btn-danger" @click="pluginAction('delete', selectedPlugin.plugin_id)">删除</button>
          </div>
          <h4 style="margin-top:18px">社区标识</h4>
          <div class="table-actions trust-switch-row">
            <button
              v-for="level in ['official', 'verified', 'community']"
              :key="level"
              :class="['btn', 'btn-sm', { 'is-active': selectedPlugin.trust_level === level }]"
              @click="setTrustLevel(selectedPlugin.plugin_id, level)"
            >{{ trustLevelLabel(level) }}</button>
          </div>
        </div>
        <div>
          <h4>当前摘要</h4>
          <ul class="meta-list">
            <li><span>Owner</span><strong>{{ selectedPlugin.owner_display_name || selectedPlugin.owner_login || selectedPlugin.owner_id }}</strong></li>
            <li><span>最新版本</span><strong>{{ selectedPlugin.latest_version || '-' }}</strong></li>
            <li><span>分类</span><strong>{{ (selectedPlugin.categories || []).map(categoryLabel).join(' / ') || '未设置' }}</strong></li>
            <li><span>标签</span><strong>{{ (selectedPlugin.tags || []).join(' / ') || '未设置' }}</strong></li>
            <li><span>热度</span><strong>{{ formatNumber(selectedPlugin.likes_count) }} 订阅 · {{ formatNumber(selectedPlugin.downloads_count) }} 下载</strong></li>
            <li><span>最近治理</span><strong>{{ formatRelative(selectedPlugin.updated_at) }}</strong></li>
          </ul>
        </div>
      </div>

      <div v-if="snapshot?.recent_reviews?.length" class="review-feed" style="margin-top:16px">
        <article v-for="item in snapshot.recent_reviews.slice(0, 6)" :key="item.id || item.created_at" class="review-feed-item">
          <div>
            <strong>{{ item.action }}</strong>
            <p>{{ item.target_id }} · {{ item.status_before || '-' }} → {{ item.status_after || '-' }}</p>
          </div>
          <div class="review-feed-meta">
            <span>{{ item.operator_id }}</span>
            <span>{{ formatRelative(item.created_at) }}</span>
          </div>
        </article>
      </div>
    </section>

    <section v-else class="panel">
      <EmptyState title="未选择插件" message="从表格中选择一个插件后，这里会展示快速治理面板。" />
    </section>

    <BulkActionBar
      :selected-count="admin.selectedIds.length"
      :pending="admin.bulkPending"
      :actions="bulkActions"
      @confirm="applyBulkAction"
    />
  </div>
</template>