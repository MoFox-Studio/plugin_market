<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import api from '@/api'
import { formatRelative } from '@/utils/format'
import type { ReviewItem } from '@/types'
import DataTable from '@/components/DataTable.vue'

const loading = ref(true)
const reviews = ref<ReviewItem[]>([])
const action = ref('')
const targetType = ref('')
const operatorId = ref('')
const fromDate = ref('')
const toDate = ref('')
const page = ref(1)
const pageSize = 20
const sortKey = ref('created_at')
const sortDirection = ref<'asc' | 'desc'>('desc')

const columns = [
  { key: 'target_type', label: '目标类型', sortable: true },
  { key: 'target_id', label: '目标 ID', sortable: true },
  { key: 'action', label: '动作', sortable: true },
  { key: 'operator_id', label: '操作人', sortable: true },
  { key: 'status_after', label: '结果状态', sortable: true, cell: (row: Record<string, unknown>) => String(row.status_after || '-') },
  { key: 'created_at', label: '时间', sortable: true, cell: (row: Record<string, unknown>) => formatRelative(String(row.created_at || '')) },
]

const filteredReviews = computed(() => {
  const next = reviews.value.filter((item) => {
    const matchesAction = !action.value || item.action === action.value
    const matchesTargetType = !targetType.value || item.target_type === targetType.value
    const matchesOperator = !operatorId.value.trim() || item.operator_id.toLowerCase().includes(operatorId.value.trim().toLowerCase())
    const createdAt = new Date(item.created_at).getTime()
    const matchesFrom = !fromDate.value || createdAt >= new Date(fromDate.value).getTime()
    const matchesTo = !toDate.value || createdAt <= new Date(`${toDate.value}T23:59:59`).getTime()
    return matchesAction && matchesTargetType && matchesOperator && matchesFrom && matchesTo
  })

  return [...next].sort((left, right) => {
    const leftValue = String((left as unknown as Record<string, unknown>)[sortKey.value] || '')
    const rightValue = String((right as unknown as Record<string, unknown>)[sortKey.value] || '')
    const direction = sortDirection.value === 'asc' ? 1 : -1
    return leftValue.localeCompare(rightValue, 'zh-CN') * direction
  })
})

const pagedReviews = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredReviews.value.slice(start, start + pageSize)
})

const actionOptions = computed(() => Array.from(new Set(reviews.value.map((item) => item.action))).sort())
const targetTypeOptions = computed(() => Array.from(new Set(reviews.value.map((item) => item.target_type))).sort())

async function loadReviews(): Promise<void> {
  loading.value = true
  try {
    reviews.value = await api.get('/api/v1/admin/reviews')
  } finally {
    loading.value = false
  }
}

function handleSort(payload: { key: string; direction: 'asc' | 'desc' }): void {
  sortKey.value = payload.key
  sortDirection.value = payload.direction
}

function exportCsv(): void {
  const header = ['target_type', 'target_id', 'action', 'status_before', 'status_after', 'reason', 'operator_id', 'created_at']
  const rows = filteredReviews.value.map((item) => [
    item.target_type,
    item.target_id,
    item.action,
    item.status_before || '',
    item.status_after || '',
    item.reason || '',
    item.operator_id,
    item.created_at,
  ])
  const csv = [header, ...rows]
    .map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(','))
    .join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'admin-audit.csv'
  link.click()
  URL.revokeObjectURL(url)
}

onMounted(() => {
  void loadReviews()
})
</script>

<template>
  <section class="admin-subview-stack">
    <section class="panel">
      <div class="section-head compact-head">
        <div>
          <h2>审计日志</h2>
          <p>基于现有 `/api/v1/admin/reviews` 提供动作、目标类型、操作人和时间过滤，并支持 CSV 导出。</p>
        </div>
        <button class="btn btn-sm" type="button" @click="exportCsv">导出 CSV</button>
      </div>

      <div class="queue-table-filters admin-plugins-filters">
        <select class="profile-editor-input" :value="action" @change="action = ($event.target as HTMLSelectElement).value; page = 1">
          <option value="">全部动作</option>
          <option v-for="item in actionOptions" :key="item" :value="item">{{ item }}</option>
        </select>
        <select class="profile-editor-input" :value="targetType" @change="targetType = ($event.target as HTMLSelectElement).value; page = 1">
          <option value="">全部目标类型</option>
          <option v-for="item in targetTypeOptions" :key="item" :value="item">{{ item }}</option>
        </select>
        <input class="profile-editor-input" :value="operatorId" type="search" placeholder="按 operator_id 搜索" @input="operatorId = ($event.target as HTMLInputElement).value; page = 1">
        <input class="profile-editor-input" :value="fromDate" type="date" @input="fromDate = ($event.target as HTMLInputElement).value; page = 1">
        <input class="profile-editor-input" :value="toDate" type="date" @input="toDate = ($event.target as HTMLInputElement).value; page = 1">
      </div>

      <DataTable
        :columns="columns"
        :rows="pagedReviews as unknown as Record<string, unknown>[]"
        row-key="created_at"
        :page="page"
        :page-size="pageSize"
        :total="filteredReviews.length"
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