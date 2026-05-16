<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

type TableAlign = 'left' | 'center' | 'right'
type TableSortDirection = 'asc' | 'desc'

interface DataTableColumn {
  key: string
  label: string
  sortable?: boolean
  align?: TableAlign
  valueKey?: string
  width?: string
  cell?: (row: Record<string, unknown>) => string | number | null | undefined
}

const props = withDefaults(defineProps<{
  columns: DataTableColumn[]
  rows: Record<string, unknown>[]
  rowKey: string | ((row: Record<string, unknown>) => string)
  selectedIds?: string[]
  sortKey?: string
  sortDirection?: TableSortDirection
  page?: number
  pageSize?: number
  total?: number
  loading?: boolean
  selectable?: boolean
}>(), {
  selectedIds: () => [],
  sortKey: '',
  sortDirection: 'asc',
  page: 1,
  pageSize: 20,
  total: 0,
  loading: false,
  selectable: true,
})

const emit = defineEmits<{
  (e: 'toggle-row', rowId: string): void
  (e: 'toggle-all', rowIds: string[]): void
  (e: 'sort', payload: { key: string; direction: TableSortDirection }): void
  (e: 'page-change', page: number): void
  (e: 'row-activate', row: Record<string, unknown>): void
}>()

const isNarrow = ref(false)
let mediaQuery: MediaQueryList | null = null

const selectableEnabled = computed(() => props.selectable && !isNarrow.value)
const rowIds = computed(() => props.rows.map((row) => resolveRowId(row)))
const selectedSet = computed(() => new Set(props.selectedIds))
const allSelected = computed(() => rowIds.value.length > 0 && rowIds.value.every((rowId) => selectedSet.value.has(rowId)))
const totalPages = computed(() => Math.max(1, Math.ceil((props.total || 0) / props.pageSize)))

function resolveRowId(row: Record<string, unknown>): string {
  if (typeof props.rowKey === 'function') {
    return props.rowKey(row)
  }
  return String(row[props.rowKey] ?? '')
}

function resolveValue(row: Record<string, unknown>, path: string): unknown {
  return path.split('.').reduce<unknown>((current, segment) => {
    if (current && typeof current === 'object' && segment in (current as Record<string, unknown>)) {
      return (current as Record<string, unknown>)[segment]
    }
    return undefined
  }, row)
}

function renderCell(row: Record<string, unknown>, column: DataTableColumn): string {
  const value = column.cell ? column.cell(row) : resolveValue(row, column.valueKey || column.key)
  return value === null || value === undefined ? '-' : String(value)
}

function toggleSort(column: DataTableColumn): void {
  if (!column.sortable) {
    return
  }
  const nextDirection: TableSortDirection = props.sortKey === column.key && props.sortDirection === 'asc' ? 'desc' : 'asc'
  emit('sort', { key: column.key, direction: nextDirection })
}

function toggleAll(): void {
  emit('toggle-all', allSelected.value ? [] : rowIds.value)
}

function updateNarrowState(): void {
  isNarrow.value = Boolean(mediaQuery?.matches)
}

onMounted(() => {
  if (typeof window === 'undefined') {
    return
  }
  mediaQuery = window.matchMedia('(max-width: 767px)')
  updateNarrowState()
  mediaQuery.addEventListener('change', updateNarrowState)
})

onBeforeUnmount(() => {
  mediaQuery?.removeEventListener('change', updateNarrowState)
})
</script>

<template>
  <div class="data-table-shell">
    <div class="data-table-scroll">
      <table class="data-table">
        <thead>
          <tr>
            <th v-if="selectableEnabled" class="data-table-check">
              <input type="checkbox" :checked="allSelected" @change="toggleAll">
            </th>
            <th v-for="column in columns" :key="column.key" :style="column.width ? { width: column.width } : undefined" :class="[`align-${column.align || 'left'}`]">
              <button v-if="column.sortable" type="button" class="data-table-sort" @click="toggleSort(column)">
                <span>{{ column.label }}</span>
                <span class="data-table-sort-indicator">{{ sortKey === column.key ? (sortDirection === 'asc' ? '↑' : '↓') : '↕' }}</span>
              </button>
              <span v-else>{{ column.label }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td :colspan="columns.length + (selectableEnabled ? 1 : 0)" class="data-table-empty">加载中…</td>
          </tr>
          <tr v-else-if="!rows.length">
            <td :colspan="columns.length + (selectableEnabled ? 1 : 0)" class="data-table-empty">暂无数据</td>
          </tr>
          <tr v-for="row in rows" v-else :key="resolveRowId(row)" :class="{ 'is-selected': selectedSet.has(resolveRowId(row)) }" @click="emit('row-activate', row)">
            <td v-if="selectableEnabled" class="data-table-check" @click.stop>
              <input type="checkbox" :checked="selectedSet.has(resolveRowId(row))" @change="emit('toggle-row', resolveRowId(row))">
            </td>
            <td v-for="column in columns" :key="column.key" :class="[`align-${column.align || 'left'}`]">{{ renderCell(row, column) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="data-table-footer">
      <small>第 {{ page }} / {{ totalPages }} 页 · 共 {{ total }} 条</small>
      <div class="data-table-pagination">
        <button class="btn btn-ghost btn-sm" type="button" :disabled="page <= 1" @click="emit('page-change', page - 1)">上一页</button>
        <button class="btn btn-ghost btn-sm" type="button" :disabled="page >= totalPages" @click="emit('page-change', page + 1)">下一页</button>
      </div>
    </div>
  </div>
</template>