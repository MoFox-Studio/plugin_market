<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue';
import api from '@/api';
import { formatNumber } from '@/utils/format';
import DataTable from '@/components/DataTable.vue';

interface AuthorRow {
  author_id: string;
  display_name: string;
  github_login: string;
  plugins_count: number;
  likes_received: number;
  downloads_total: number;
  admin_flag: string;
}

const loading = ref(true);
const error = ref('');
let requestId = 0;
const query = ref('');
const authors = ref<AuthorRow[]>([]);
const page = ref(1);
const pageSize = 20;
const sortKey = ref('downloads_total');
const sortDirection = ref<'asc' | 'desc'>('desc');

const columns = [
  {
    key: 'display_name',
    label: '作者',
    sortable: true,
    cell: (row: Record<string, unknown>) =>
      `${String(row.display_name || '-')} · @${String(row.github_login || '-')}`,
  },
  { key: 'author_id', label: 'Author ID', sortable: true },
  {
    key: 'plugins_count',
    label: '插件数',
    sortable: true,
    align: 'right' as const,
  },
  {
    key: 'likes_received',
    label: '获订阅',
    sortable: true,
    align: 'right' as const,
    cell: (row: Record<string, unknown>) =>
      formatNumber(Number(row.likes_received || 0)),
  },
  {
    key: 'downloads_total',
    label: '下载',
    sortable: true,
    align: 'right' as const,
    cell: (row: Record<string, unknown>) =>
      formatNumber(Number(row.downloads_total || 0)),
  },
];

const filteredAuthors = computed(() => {
  const next = authors.value.filter((item) => {
    const needle = query.value.trim().toLowerCase();
    return (
      !needle ||
      [item.author_id, item.display_name, item.github_login].some((value) =>
        value.toLowerCase().includes(needle),
      )
    );
  });

  return [...next].sort((left, right) => {
    const leftValue =
      (left as unknown as Record<string, unknown>)[sortKey.value] ?? '';
    const rightValue =
      (right as unknown as Record<string, unknown>)[sortKey.value] ?? '';
    const direction = sortDirection.value === 'asc' ? 1 : -1;
    return (
      (typeof leftValue === 'number' && typeof rightValue === 'number'
        ? leftValue - rightValue
        : String(leftValue).localeCompare(String(rightValue), 'zh-CN', {
            numeric: true,
          })) * direction
    );
  });
});

const pagedAuthors = computed(() => {
  const start = (page.value - 1) * pageSize;
  return filteredAuthors.value.slice(start, start + pageSize);
});

async function loadAuthors(): Promise<void> {
  const current = ++requestId;
  loading.value = true;
  error.value = '';
  try {
    const result = await api.get('/api/v1/admin/plugins');
    if (current !== requestId) return;
    const items = result.items || [];
    const map = new Map<string, AuthorRow>();
    for (const plugin of items) {
      const existing = map.get(plugin.owner_id);
      if (existing) {
        existing.plugins_count += 1;
        existing.likes_received += plugin.likes_count;
        existing.downloads_total += plugin.downloads_count;
        continue;
      }
      map.set(plugin.owner_id, {
        author_id: plugin.owner_id,
        display_name:
          plugin.owner_display_name || plugin.owner_login || plugin.owner_id,
        github_login: plugin.owner_login || plugin.owner_id,
        plugins_count: 1,
        likes_received: plugin.likes_count,
        downloads_total: plugin.downloads_count,
        admin_flag: '后端未暴露',
      });
    }
    authors.value = Array.from(map.values());
  } catch (e) {
    if (current === requestId)
      error.value = (e as Error).message || '无法读取作者列表';
  } finally {
    if (current === requestId) loading.value = false;
  }
}

function handleSort(payload: { key: string; direction: 'asc' | 'desc' }): void {
  sortKey.value = payload.key;
  sortDirection.value = payload.direction;
}

onMounted(() => {
  void loadAuthors();
});
onBeforeUnmount(() => {
  requestId++;
});
</script>

<template>
  <section class="admin-subview-stack">
    <section class="panel">
      <div class="section-head compact-head">
        <div>
          <h1 class="desk-title">作者名录</h1>
          <p>按插件档案汇总作者的发布规模、订阅与下载。此列表为只读概览。</p>
        </div>
      </div>
      <fieldset class="queue-table-filters admin-plugins-filters">
        <legend>查找作者</legend>
        <label class="desk-field">
          <span>姓名 / 账号 / ID</span>
          <input
            class="profile-editor-input"
            :value="query"
            type="search"
            aria-label="搜索作者"
            placeholder="搜索作者名称、GitHub 账号或 ID"
            @input="
              query = ($event.target as HTMLInputElement).value;
              page = 1;
            "
          />
        </label>
      </fieldset>
      <div v-if="error" class="admin-error" role="alert">
        <p>{{ error }}</p>
        <button class="btn" @click="loadAuthors">重新加载</button>
      </div>
      <DataTable
        v-else
        caption="作者发布记录"
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
