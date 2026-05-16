<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import api from '@/api'
import { useToastStore } from '@/stores/toast'
import { formatRelative } from '@/utils/format'
import type { Comment, Plugin } from '@/types'
import EmptyState from '@/components/EmptyState.vue'

interface CommentListResponse {
  items: Comment[]
  total: number
}

const toast = useToastStore()

const loadingPlugins = ref(true)
const loadingComments = ref(false)
const plugins = ref<Plugin[]>([])
const selectedPluginId = ref('')
const comments = ref<Comment[]>([])
const total = ref(0)
const query = ref('')
const showDeleted = ref(true)

const filteredComments = computed(() => comments.value.filter((item) => {
  const matchesQuery = !query.value.trim() || item.content.toLowerCase().includes(query.value.trim().toLowerCase()) || String(item.author.display_name || '').toLowerCase().includes(query.value.trim().toLowerCase())
  const matchesDeleted = showDeleted.value || !item.is_deleted
  return matchesQuery && matchesDeleted
}))

async function loadPlugins(): Promise<void> {
  loadingPlugins.value = true
  try {
    const result = await api.get('/api/v1/admin/plugins')
    plugins.value = result.items || []
    if (!selectedPluginId.value && plugins.value.length) {
      selectedPluginId.value = plugins.value[0].plugin_id
    }
  } finally {
    loadingPlugins.value = false
  }
}

async function loadComments(): Promise<void> {
  if (!selectedPluginId.value) {
    comments.value = []
    total.value = 0
    return
  }
  loadingComments.value = true
  try {
    const result = await api.get<CommentListResponse>(`/api/v1/plugins/${encodeURIComponent(selectedPluginId.value)}/comments?limit=100`)
    comments.value = result.items || []
    total.value = result.total || 0
  } catch (error) {
    toast.show((error as Error).message || '加载评论失败', 'error')
  } finally {
    loadingComments.value = false
  }
}

async function deleteComment(commentId: string): Promise<void> {
  if (!selectedPluginId.value) {
    return
  }
  if (!confirm(`确认删除评论 #${commentId} 吗？`)) {
    return
  }
  try {
    await api.del(`/api/v1/plugins/${encodeURIComponent(selectedPluginId.value)}/comments/${encodeURIComponent(commentId)}`)
    toast.show('评论已删除', 'ok')
    await loadComments()
  } catch (error) {
    toast.show((error as Error).message || '删除失败', 'error')
  }
}

watch(selectedPluginId, () => {
  void loadComments()
})

onMounted(async () => {
  await loadPlugins()
  await loadComments()
})
</script>

<template>
  <section class="admin-subview-stack">
    <section class="panel">
      <div class="section-head compact-head">
        <div>
          <h2>评论审核</h2>
          <p>当前基于插件评论接口做聚合查看；删除可直接执行，恢复仅做显示占位。</p>
        </div>
      </div>

      <div class="queue-table-filters admin-plugins-filters">
        <select class="profile-editor-input" :value="selectedPluginId" :disabled="loadingPlugins" @change="selectedPluginId = ($event.target as HTMLSelectElement).value">
          <option value="">选择插件</option>
          <option v-for="plugin in plugins" :key="plugin.plugin_id" :value="plugin.plugin_id">{{ plugin.display_name }} · {{ plugin.plugin_id }}</option>
        </select>
        <input class="profile-editor-input" :value="query" type="search" placeholder="搜索评论内容或作者" @input="query = ($event.target as HTMLInputElement).value">
        <label class="admin-filter-toggle">
          <input :checked="showDeleted" type="checkbox" @change="showDeleted = ($event.target as HTMLInputElement).checked">
          <span>显示已删除评论</span>
        </label>
      </div>
    </section>

    <section class="panel" v-if="selectedPluginId">
      <div class="section-head compact-head">
        <div>
          <h2>评论列表</h2>
          <p>当前插件共 {{ total }} 条评论，展示最近 100 条。</p>
        </div>
      </div>
      <div v-if="loadingComments" class="inbox-list-state">加载评论中…</div>
      <div v-else-if="filteredComments.length" class="review-feed">
        <article v-for="item in filteredComments" :key="item.id" class="review-feed-item">
          <div>
            <strong>{{ item.author.display_name }} · @{{ item.author.github_login }}</strong>
            <p>{{ item.content }}</p>
            <small class="soft-note">{{ formatRelative(item.created_at) }} · {{ item.is_deleted ? '已删除' : '可见' }}</small>
          </div>
          <div class="table-actions">
            <button v-if="!item.is_deleted" class="btn btn-sm btn-danger" type="button" @click="deleteComment(item.id)">删除</button>
            <button class="btn btn-sm btn-ghost" type="button" disabled>还原待后端支持</button>
          </div>
        </article>
      </div>
      <EmptyState v-else title="暂无评论" message="换一个插件或放宽筛选条件试试。" />
    </section>
  </section>
</template>