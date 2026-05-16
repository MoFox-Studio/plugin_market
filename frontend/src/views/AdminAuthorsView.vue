<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import api from '@/api'
import { formatNumber } from '@/utils/format'
import DataTable from '@/components/DataTable.vue'

interface AuthorRow {
  author_id: string
  display_name: string
  github_login: string
  plugins_count: number
  likes_received: number
  downloads_total: number
  admin_flag: string
}

const loading = ref(true)
const query = ref('')
const authors = ref<AuthorRow[]>([])
const page = ref(1)
const pageSize = 20
const sortKey = ref('downloads_total')
const sortDirection = ref<'asc' | 'desc'>('desc')

const columns = [
  { key: 'display_name', label: '作者', sortable: true, cell: (row: Record<string, unknown>) => `${String(row.display_name || '-')} · @${String(row.github_login || '-')}` },
  { key: 'author_id', label: 'Author ID', sortable: true },
  { key: 'plugins_count', label: '插件数', sortable: true, align: 'right' as const },
  { key: 'likes_received', label: '获赞', sortable: true, align: 'right' as const, cell: (row: Record<string, unknown>) => formatNumber(Number(row.likes_received || 0)) },
  { key: 'downloads_total', label: '下载', sortable: true, align: 'right' as const, cell: (row: Record<string, unknown>) => formatNumber(Number(row.downloads_total || 0)) },
  { key: 'admin_flag', label: 'Admin 标志', sortable: true },
]

const filteredAuthors = computed(() => {
  const next = authors.value.filter((item) => {
    const needle = query.value.trim().toLowerCase()
    return !needle || [item.author_id, item.display_name, item.github_login].some((value) => value.toLowerCase().includes(needle))
  })

  return [...next].sort((left, right) => {
    const leftValue = String((left as unknown as Record<string, unknown>)[sortKey.value] || '')
    const rightValue = String((right as unknown as Record<string, unknown>)[sortKey.value] || '')
    const direction = sortDirection.value === 'asc' ? 1 : -1
    return leftValue.localeCompare(rightValue, 'zh-CN') * direction
  })
})

const pagedAuthors = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredAuthors.value.slice(start, start + pageSize)
})

async function loadAuthors(): Promise<void> {
  loading.value = true
  try {
    const result = await api.get('/api/v1/admin/plugins')
    const items = result.items || []
    const map = new Map<string, AuthorRow>()
    for (const plugin of items) {
      const existing = map.get(plugin.owner_id)
      if (existing) {
        existing.plugins_count += 1
        existing.likes_received += plugin.likes_count
        existing.downloads_total += plugin.downloads_count
        continue
      }
      map.set(plugin.owner_id, {
        author_id: plugin.owner_id,
        display_name: plugin.owner_display_name || plugin.owner_login || plugin.owner_id,
        github_login: plugin.owner_login || plugin.owner_id,
        plugins_count: 1,
        likes_received: plugin.likes_count,
        downloads_total: plugin.downloads_count,
        admin_flag: '后端未暴露',
      })
    }
    authors.value = Array.from(map.values())
  } finally {
    loading.value = false
  }
}

function handleSort(payload: { key: string; direction: 'asc' | 'desc' }): void {
  sortKey.value = payload.key
  sortDirection.value = payload.direction
}

onMounted(() => {
  void loadAuthors()
})
</script>

<template>
  <section class="admin-subview-stack">
    <section class="panel">
      <div class="section-head compact-head">
        <div>
          <h2>作者管理</h2>
          <p>当前后端未暴露作者 admin toggle 接口，因此这里先提供只读作者列表与规模信息。</p>
        </div>
      </div>
      <div class="queue-table-filters admin-plugins-filters">
        <input class="profile-editor-input" :value="query" type="search" placeholder="搜索作者 display_name / login / id" @input="query = ($event.target as HTMLInputElement).value; page = 1">
      </div>
      <DataTable
        :columns="columns"
        :rows="pagedAuthors as unknown as Record<string, unknown>[]"
        row-key="author_id"
        :page="page"
        :page-size="pageSize"
        :total="filteredAuthors.length"
        :sort-key="sortKey"
        :sort-direction="sortDirection"
        :selectable="false"
        :loading="loading"
        @sort="handleSort"
        @page-change="page = $event"
      />
    </section>
  </section>
</template>