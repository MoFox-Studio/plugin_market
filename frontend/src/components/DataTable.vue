<script setup lang="ts">
import { computed } from 'vue';
import PageSkeleton from '@/components/PageSkeleton.vue';

type TableAlign = 'left' | 'center' | 'right';
type TableSortDirection = 'asc' | 'desc';

interface DataTableColumn {
  key: string;
  label: string;
  sortable?: boolean;
  align?: TableAlign;
  valueKey?: string;
  width?: string;
  cell?: (row: Record<string, unknown>) => string | number | null | undefined;
}

const props = withDefaults(
  defineProps<{
    caption: string;
    columns: DataTableColumn[];
    rows: Record<string, unknown>[];
    rowKey: string | ((row: Record<string, unknown>) => string);
    selectedIds?: string[];
    sortKey?: string;
    sortDirection?: TableSortDirection;
    page?: number;
    pageSize?: number;
    total?: number;
    loading?: boolean;
    selectable?: boolean;
    activatable?: boolean;
  }>(),
  {
    selectedIds: () => [],
    sortKey: '',
    sortDirection: 'asc',
    page: 1,
    pageSize: 20,
    total: 0,
    loading: false,
    selectable: true,
    activatable: false,
  },
);

const emit = defineEmits<{
  (e: 'toggle-row', rowId: string): void;
  (e: 'toggle-all', rowIds: string[]): void;
  (e: 'sort', payload: { key: string; direction: TableSortDirection }): void;
  (e: 'page-change', page: number): void;
  (e: 'row-activate', row: Record<string, unknown>): void;
}>();

const selectableEnabled = computed(() => props.selectable);
const rowIds = computed(() => props.rows.map((row) => resolveRowId(row)));
const selectedSet = computed(() => new Set(props.selectedIds));
const allSelected = computed(
  () =>
    rowIds.value.length > 0 &&
    rowIds.value.every((rowId) => selectedSet.value.has(rowId)),
);
const totalPages = computed(() =>
  Math.max(1, Math.ceil((props.total || 0) / props.pageSize)),
);

function resolveRowId(row: Record<string, unknown>): string {
  if (typeof props.rowKey === 'function') {
    return props.rowKey(row);
  }
  return String(row[props.rowKey] ?? '');
}

function resolveValue(row: Record<string, unknown>, path: string): unknown {
  return path.split('.').reduce<unknown>((current, segment) => {
    if (
      current &&
      typeof current === 'object' &&
      segment in (current as Record<string, unknown>)
    ) {
      return (current as Record<string, unknown>)[segment];
    }
    return undefined;
  }, row);
}

function renderCell(
  row: Record<string, unknown>,
  column: DataTableColumn,
): string {
  const value = column.cell
    ? column.cell(row)
    : resolveValue(row, column.valueKey || column.key);
  return value === null || value === undefined ? '-' : String(value);
}

function toggleSort(column: DataTableColumn): void {
  if (!column.sortable) {
    return;
  }
  const nextDirection: TableSortDirection =
    props.sortKey === column.key && props.sortDirection === 'asc'
      ? 'desc'
      : 'asc';
  emit('sort', { key: column.key, direction: nextDirection });
}

function activateWithKeyboard(
  event: KeyboardEvent,
  row: Record<string, unknown>,
): void {
  if (
    !props.activatable ||
    event.target !== event.currentTarget ||
    !['Enter', ' '].includes(event.key)
  )
    return;
  event.preventDefault();
  emit('row-activate', row);
}

function toggleAll(): void {
  emit('toggle-all', allSelected.value ? [] : rowIds.value);
}
</script>

<template>
  <div class="data-table-shell">
    <div class="data-table-scroll" tabindex="0" role="region" :aria-label="caption">
      <table class="data-table">
        <caption>{{ caption }}</caption>
        <thead>
          <tr>
            <th v-if="selectableEnabled" scope="col" class="data-table-check">
              <input
                type="checkbox"
                aria-label="选择当前页全部项目"
                :disabled="loading || !rows.length"
                :indeterminate="
                  !allSelected && rowIds.some((id) => selectedSet.has(id))
                "
                :checked="allSelected"
                @change="toggleAll"
              />
            </th>
            <th
              v-for="column in columns"
              :key="column.key"
              scope="col"
              :aria-sort="
                column.sortable
                  ? sortKey === column.key
                    ? sortDirection === 'asc'
                      ? 'ascending'
                      : 'descending'
                    : 'none'
                  : undefined
              "
              :style="column.width ? { width: column.width } : undefined"
              :class="[`align-${column.align || 'left'}`]"
            >
              <button
                v-if="column.sortable"
                type="button"
                class="data-table-sort"
                @click="toggleSort(column)"
              >
                <span>{{ column.label }}</span>
                <span class="data-table-sort-indicator" aria-hidden="true">{{
                  sortKey === column.key
                    ? sortDirection === 'asc'
                      ? '↑'
                      : '↓'
                    : '↕'
                }}</span>
              </button>
              <span v-else>{{ column.label }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td
              :colspan="columns.length + (selectableEnabled ? 1 : 0)"
              class="data-table-empty"
            >
              <PageSkeleton type="rows" :count="4" />
            </td>
          </tr>
          <tr v-else-if="!rows.length">
            <td
              :colspan="columns.length + (selectableEnabled ? 1 : 0)"
              class="data-table-empty"
            >
              暂无数据
            </td>
          </tr>
          <tr
            v-for="row in rows"
            v-else
            :key="resolveRowId(row)"
            :class="{
              'is-selected': selectedSet.has(resolveRowId(row)),
              'is-actionable': activatable,
            }"
            :tabindex="activatable ? 0 : undefined"
            @click="activatable && emit('row-activate', row)"
            @keydown="activateWithKeyboard($event, row)"
          >
            <td v-if="selectableEnabled" class="data-table-check" @click.stop>
              <input
                type="checkbox"
                :aria-label="`选择项目 ${resolveRowId(row)}`"
                :checked="selectedSet.has(resolveRowId(row))"
                @change="emit('toggle-row', resolveRowId(row))"
              />
            </td>
            <td
              v-for="column in columns"
              :key="column.key"
              :class="[`align-${column.align || 'left'}`]"
            >
              {{ renderCell(row, column) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="data-table-footer">
      <small>第 {{ page }} / {{ totalPages }} 页 · 共 {{ total }} 条</small>
      <div class="data-table-pagination">
        <button
          class="btn btn-ghost btn-sm"
          type="button"
          :disabled="page <= 1 || loading"
          @click="emit('page-change', page - 1)"
        >
          上一页
        </button>
        <button
          class="btn btn-ghost btn-sm"
          type="button"
          :disabled="page >= totalPages || loading"
          @click="emit('page-change', page + 1)"
        >
          下一页
        </button>
      </div>
    </div>
  </div>
</template>
<style scoped>
.data-table-shell {
  min-width: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.data-table-scroll {
  max-width: 100%;
  overflow: auto;
  border-block: 2px solid var(--ink-700);
}
.data-table-scroll:focus-visible {
  outline: 2px solid var(--blue-500);
  outline-offset: 2px;
}
.data-table caption {
  padding: 13px 4px;
  border-bottom: 1px solid var(--ink-700);
  color: var(--ink-900);
  font: 650 19px/1.3 var(--font-editorial);
  text-align: left;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  text-align: left;
}
.data-table th {
  background: var(--surface-soft);
  padding: 11px 12px;
  color: var(--ink-700);
  font-weight: 500;
  white-space: nowrap;
  border-bottom: 1px solid var(--line);
}
.data-table td {
  padding: 13px 12px;
  border-bottom: 1px solid var(--line);
  white-space: nowrap;
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.data-table tr:last-child td {
  border-bottom: 0;
}
.data-table tbody tr:hover {
  background: var(--surface-soft);
}
.data-table tbody tr.is-selected {
  background: var(--blue-50);
}
.data-table .is-actionable {
  cursor: pointer;
}
.data-table .is-actionable:focus-visible {
  outline: 2px solid var(--blue-500);
  outline-offset: -2px;
}
.data-table-check {
  width: 42px;
}
.data-table input[type='checkbox'] {
  width: 15px;
  height: 15px;
  accent-color: var(--blue-600);
}
.data-table-sort {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  white-space: nowrap;
  font-size: inherit;
  padding: 0;
  color: inherit;
}
.data-table-sort-indicator {
  color: var(--blue-600);
  font-size: 10px;
}
.align-right {
  text-align: right;
}
.align-center {
  text-align: center;
}
.data-table .data-table-empty {
  max-width: none;
  white-space: normal;
  text-align: center;
  padding: 32px;
  color: var(--ink-500);
  height: 170px;
}
.data-table-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-top: 0;
  padding: 12px 0;
  background: transparent;
  border: 0;
}
.data-table-footer small {
  color: var(--ink-500);
  font: 11px var(--font-mono);
}
.data-table-pagination {
  display: flex;
  gap: 8px;
}
@media (max-width: 600px) {
  .data-table-footer {
    flex-wrap: wrap;
  }
  .data-table td {
    padding: 14px 12px;
  }
}
</style>
