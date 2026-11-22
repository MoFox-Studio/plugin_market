<script setup lang="ts">
import { useMarketDialog } from '@/composables/useMarketDialog';
const { confirm: confirmAction, prompt: promptAction } = useMarketDialog();
import MarketSelect from '@/components/MarketSelect.vue';
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import api from '@/api';
import { useAdminStore } from '@/stores/admin';
import { useTaxonomyStore } from '@/stores/taxonomy';
import { useToastStore } from '@/stores/toast';
import {
  formatNumber,
  formatRelative,
  statusText,
  trustLevelLabel,
  categoryLabel,
} from '@/utils/format';
import type { BulkAction, Plugin, PluginSnapshot } from '@/types';
import PageSkeleton from '@/components/PageSkeleton.vue';
import DataTable from '@/components/DataTable.vue';
import BulkActionBar from '@/components/BulkActionBar.vue';
import EmptyState from '@/components/EmptyState.vue';
import TrustBadge from '@/components/TrustBadge.vue';

const admin = useAdminStore();
const taxonomy = useTaxonomyStore();
const toast = useToastStore();

const plugins = ref<Plugin[]>([]);
const selectedId = ref<string | null>(null);
const selectedPlugin = ref<Plugin | null>(null);
const snapshot = ref<PluginSnapshot | null>(null);
const loading = ref(true);
const error = ref('');
const snapshotError = ref('');
const snapshotLoading = ref(false);
const actionPending = ref(false);
let listRequest = 0;
let snapshotRequest = 0;
let disposed = false;
const sortKey = ref('updated_at');
const sortDirection = ref<'asc' | 'desc'>('desc');

const tableColumns = [
  {
    key: 'display_name',
    label: '插件名称',
    sortable: true,
    cell: (row: Record<string, unknown>) => String(row.display_name || '-'),
  },
  {
    key: 'owner_display_name',
    label: '作者',
    sortable: true,
    cell: (row: Record<string, unknown>) =>
      String(row.owner_display_name || row.owner_login || row.owner_id || '-'),
  },
  {
    key: 'status',
    label: '状态',
    sortable: true,
    cell: (row: Record<string, unknown>) =>
      statusText(String(row.status || '')),
  },
  {
    key: 'trust_level',
    label: '社区标识',
    sortable: true,
    cell: (row: Record<string, unknown>) =>
      trustLevelLabel(String(row.trust_level || '')),
  },
  {
    key: 'latest_version',
    label: '最新版本',
    sortable: true,
    cell: (row: Record<string, unknown>) => String(row.latest_version || '-'),
  },
  {
    key: 'likes_count',
    label: '订阅',
    sortable: true,
    align: 'right' as const,
    cell: (row: Record<string, unknown>) =>
      formatNumber(Number(row.likes_count || 0)),
  },
  {
    key: 'downloads_count',
    label: '下载',
    sortable: true,
    align: 'right' as const,
    cell: (row: Record<string, unknown>) =>
      formatNumber(Number(row.downloads_count || 0)),
  },
  {
    key: 'comments_count',
    label: '评论',
    sortable: true,
    align: 'right' as const,
    cell: (row: Record<string, unknown>) =>
      formatNumber(Number(row.comments_count || 0)),
  },
  {
    key: 'updated_at',
    label: '最近治理时间',
    sortable: true,
    cell: (row: Record<string, unknown>) =>
      formatRelative(String(row.updated_at || '')),
  },
];

const bulkActions: Array<{
  key: BulkAction;
  label: string;
  variant?: 'default' | 'danger';
  requireReason?: boolean;
}> = [
  { key: 'publish', label: '批量上架' },
  { key: 'reject', label: '批量退回' },
  { key: 'deprecate', label: '批量下架' },
  { key: 'block', label: '批量封禁', variant: 'danger' as const },
  {
    key: 'delete',
    label: '批量删除',
    variant: 'danger' as const,
    requireReason: true,
  },
];

const filteredPlugins = computed(() => {
  const query = admin.filters.query.trim().toLowerCase();
  const status = admin.filters.status;
  const trustLevel = admin.filters.trustLevel;
  const owner = admin.filters.owner.trim().toLowerCase();
  const category = admin.filters.category;
  const tag = admin.filters.tag.trim().toLowerCase();
  const pendingOnly = admin.filters.pendingOnly;

  const next = plugins.value.filter((plugin) => {
    const matchesQuery =
      !query ||
      [
        plugin.display_name,
        plugin.plugin_id,
        plugin.summary,
        plugin.owner_display_name,
        plugin.owner_login,
        plugin.owner_id,
      ].some((value) =>
        String(value || '')
          .toLowerCase()
          .includes(query),
      );
    const matchesStatus = !status || plugin.status === status;
    const matchesTrust = !trustLevel || plugin.trust_level === trustLevel;
    const ownerText = [
      plugin.owner_display_name,
      plugin.owner_login,
      plugin.owner_id,
    ].map((value) => String(value || '').toLowerCase());
    const matchesOwner =
      !owner || ownerText.some((value) => value.includes(owner));
    const matchesCategory =
      !category || (plugin.categories || []).includes(category);
    const matchesTag =
      !tag ||
      (plugin.tags || []).some((item) => item.toLowerCase().includes(tag));
    const matchesPending = !pendingOnly || plugin.status === 'pending_review';
    return (
      matchesQuery &&
      matchesStatus &&
      matchesTrust &&
      matchesOwner &&
      matchesCategory &&
      matchesTag &&
      matchesPending
    );
  });

  const sorted = [...next].sort((left, right) => {
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

  return sorted;
});

watch(
  () => filteredPlugins.value.length,
  (total) => {
    admin.setPagination({
      total,
      page: Math.min(
        admin.pagination.page,
        Math.max(1, Math.ceil(total / admin.pagination.pageSize)),
      ),
    });
  },
  { immediate: true },
);

const pagedPlugins = computed(() => {
  const start = (admin.pagination.page - 1) * admin.pagination.pageSize;
  return filteredPlugins.value.slice(start, start + admin.pagination.pageSize);
});

const pendingCount = computed(
  () =>
    plugins.value.filter((plugin) => plugin.status === 'pending_review').length,
);

async function loadPlugins(): Promise<void> {
  if (disposed) return;
  const request = ++listRequest;
  loading.value = true;
  error.value = '';
  try {
    const [pluginResult] = await Promise.all([
      api.get('/api/v1/admin/plugins'),
      taxonomy.load(),
    ]);
    if (request !== listRequest || disposed) return;
    plugins.value = pluginResult.items || [];
    admin.setSelection(
      admin.selectedIds.filter((id) =>
        plugins.value.some((plugin) => plugin.plugin_id === id),
      ),
    );
    if (
      !plugins.value.some((plugin) => plugin.plugin_id === selectedId.value)
    ) {
      selectedId.value =
        plugins.value.find((plugin) => plugin.status === 'pending_review')
          ?.plugin_id ||
        plugins.value[0]?.plugin_id ||
        null;
    }
    void loadSnapshot();
  } catch (e) {
    if (request === listRequest && !disposed)
      error.value = (e as Error).message || '无法读取插件列表';
  } finally {
    if (request === listRequest && !disposed) loading.value = false;
  }
}

async function loadSnapshot(): Promise<void> {
  const request = ++snapshotRequest;
  const id = selectedId.value;
  selectedPlugin.value = null;
  snapshot.value = null;
  snapshotError.value = '';
  if (!id || disposed) {
    snapshotLoading.value = false;
    return;
  }
  snapshotLoading.value = true;
  try {
    const result = await api.get(
      `/api/v1/admin/plugins/${encodeURIComponent(id)}`,
    );
    if (request !== snapshotRequest || disposed) return;
    snapshot.value = result;
    selectedPlugin.value = result.plugin;
  } catch (e) {
    if (request === snapshotRequest && !disposed)
      snapshotError.value = (e as Error).message || '无法读取插件详情';
  } finally {
    if (request === snapshotRequest && !disposed) snapshotLoading.value = false;
  }
}

async function selectPlugin(id: string): Promise<void> {
  selectedId.value = id;
  await loadSnapshot();
}

async function pluginAction(action: string, pluginId: string): Promise<void> {
  if (
    actionPending.value ||
    disposed ||
    !(await confirmAction(`确认执行 ${action} 操作：${pluginId} ？`))
  )
    return;
  const reason =
    action === 'delete'
      ? ''
      : await promptAction('可填写操作原因，留空也可以。', '');
  if (reason === null) return;
  actionPending.value = true;
  try {
    if (action === 'delete') {
      await api.del(`/api/v1/admin/plugins/${encodeURIComponent(pluginId)}`);
      if (selectedId.value === pluginId) {
        selectedId.value = null;
        snapshot.value = null;
        selectedPlugin.value = null;
      }
    } else {
      await api.post(
        `/api/v1/admin/plugins/${encodeURIComponent(pluginId)}/${action}`,
        reason.trim() ? { reason: reason.trim() } : {},
      );
    }
    if (disposed) return;
    toast.show(action === 'delete' ? '插件已删除' : '治理动作已执行', 'ok');
    await loadPlugins();
  } catch (e) {
    if (!disposed) toast.show((e as Error).message || '操作失败', 'error');
  } finally {
    actionPending.value = false;
  }
}

async function setTrustLevel(pluginId: string, level: string): Promise<void> {
  if (
    actionPending.value ||
    disposed ||
    selectedPlugin.value?.trust_level === level
  )
    return;
  const reason = await promptAction(
    `可填写切换为"${trustLevelLabel(level)}"的原因，留空也可以。`,
    '',
  );
  if (reason === null) return;
  actionPending.value = true;
  try {
    await api.post(
      `/api/v1/admin/plugins/${encodeURIComponent(pluginId)}/trust-level/${encodeURIComponent(level)}`,
      reason.trim() ? { reason: reason.trim() } : {},
    );
    if (disposed) return;
    toast.show('社区标识已更新', 'ok');
    await loadPlugins();
  } catch (e) {
    if (!disposed) toast.show((e as Error).message || '切换失败', 'error');
  } finally {
    actionPending.value = false;
  }
}

function handleSort(payload: { key: string; direction: 'asc' | 'desc' }): void {
  sortKey.value = payload.key;
  sortDirection.value = payload.direction;
}

function handlePageChange(page: number): void {
  admin.setPagination({ page });
}

function handleFilter<
  K extends 'query' | 'status' | 'trustLevel' | 'owner' | 'category' | 'tag',
>(key: K, value: string): void {
  admin.setFilter(key, value);
  admin.setPagination({ page: 1 });
}

function handlePendingToggle(nextValue: boolean): void {
  admin.setFilter('pendingOnly', nextValue);
  admin.setPagination({ page: 1 });
}

function toggleSelection(pluginId: string): void {
  admin.toggleSelection(pluginId);
}

function toggleAllSelection(pluginIds: string[]): void {
  admin.setSelection(pluginIds);
}

async function applyBulkAction(payload: {
  action: BulkAction;
  params: Record<string, unknown>;
}): Promise<void> {
  if (disposed || admin.bulkPending) return;
  try {
    const result = await admin.applyBulk(payload.action, payload.params);
    if (disposed) return;
    const failures = result.results.filter((item) => !item.ok);
    if (failures.length) {
      toast.show(`批量操作完成，但有 ${failures.length} 项失败`, 'error');
    } else {
      toast.show('批量操作已完成', 'ok');
    }
    admin.clearSelection();
    await loadPlugins();
  } catch (error) {
    toast.show((error as Error).message || '批量操作失败', 'error');
  }
}

onMounted(() => {
  admin.clearSelection();
  void loadPlugins();
});
onBeforeUnmount(() => {
  disposed = true;
  listRequest++;
  snapshotRequest++;
  admin.clearSelection();
});
</script>

<template>
  <div class="admin-plugins-view">
    <section class="panel">
      <div class="section-head compact-head">
        <div>
          <h1 class="desk-title">插件治理</h1>
          <p>选择一行查看插件档案，勾选条目可批量处理。</p>
        </div>
        <div class="desk-counts">
          <span>匹配 <b>{{ admin.pagination.total }}</b> 项</span>
          <span>待审核 <b>{{ pendingCount }}</b> 项</span>
        </div>
      </div>

      <fieldset class="queue-table-filters admin-plugins-filters">
        <legend>筛选插件</legend>
        <label class="desk-field">
          <span>名称 / 摘要</span>
          <input
            class="profile-editor-input"
            :value="admin.filters.query"
            type="search"
            aria-label="搜索插件"
            placeholder="搜索插件 / 摘要 / 作者 / ID"
            @input="
              handleFilter('query', ($event.target as HTMLInputElement).value)
            "
          />
        </label>
        <label class="desk-field">
          <span>发布状态</span>
          <MarketSelect
            class="profile-editor-input"
            aria-label="插件状态"
            :value="admin.filters.status"
            @change="
              handleFilter('status', ($event.target as HTMLSelectElement).value)
            "
          >
            <option value="">全部状态</option>
            <option value="published">已发布</option>
            <option value="pending_review">待审核</option>
            <option value="draft">草稿</option>
            <option value="deprecated">已下架</option>
            <option value="blocked">已封禁</option>
          </MarketSelect>
        </label>
        <label class="desk-field">
          <span>社区标识</span>
          <MarketSelect
            class="profile-editor-input"
            aria-label="社区标识"
            :value="admin.filters.trustLevel"
            @change="
              handleFilter(
                'trustLevel',
                ($event.target as HTMLSelectElement).value,
              )
            "
          >
            <option value="">全部标识</option>
            <option value="official">官方</option>
            <option value="verified">认证</option>
            <option value="community">社区</option>
          </MarketSelect>
        </label>
        <label class="desk-field">
          <span>作者</span>
          <input
            class="profile-editor-input"
            aria-label="作者"
            :value="admin.filters.owner"
            type="search"
            placeholder="作者名、账号或 ID"
            @input="
              handleFilter('owner', ($event.target as HTMLInputElement).value)
            "
          />
        </label>
        <label class="desk-field">
          <span>分类</span>
          <MarketSelect
            class="profile-editor-input"
            aria-label="分类"
            :value="admin.filters.category"
            @change="
              handleFilter('category', ($event.target as HTMLSelectElement).value)
            "
          >
            <option value="">全部分类</option>
            <option v-for="item in taxonomy.categories" :key="item" :value="item">
              {{ categoryLabel(item) }}
            </option>
          </MarketSelect>
        </label>
        <label class="desk-field">
          <span>标签</span>
          <input
            class="profile-editor-input"
            aria-label="标签"
            :value="admin.filters.tag"
            type="search"
            placeholder="输入标签"
            @input="
              handleFilter('tag', ($event.target as HTMLInputElement).value)
            "
          />
        </label>
        <label class="admin-filter-toggle">
          <input
            :checked="admin.filters.pendingOnly"
            type="checkbox"
            @change="
              handlePendingToggle(($event.target as HTMLInputElement).checked)
            "
          />
          <span>只看待审核</span>
        </label>
      </fieldset>

      <div v-if="error" class="admin-error" role="alert">
        <p>{{ error }}</p>
        <button class="btn" @click="loadPlugins">重新加载</button>
      </div>

      <DataTable
        v-else
        caption="插件治理名录"
        activatable
        :loading="loading"
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

    <section v-if="snapshotLoading" class="panel">
      <PageSkeleton type="detail" />
    </section>
    <section v-else-if="snapshotError" class="panel admin-error" role="alert">
      <p>{{ snapshotError }}</p>
      <button class="btn" @click="loadSnapshot">重新加载详情</button>
    </section>
    <section class="panel" v-else-if="selectedPlugin">
      <div class="section-head compact-head">
        <div>
          <h2>{{ selectedPlugin.display_name }}</h2>
          <p>{{ selectedPlugin.summary }}</p>
        </div>
        <div class="table-actions">
          <TrustBadge :level="selectedPlugin.trust_level" />
          <span :class="['badge', `status-${selectedPlugin.status}`]">{{
            statusText(selectedPlugin.status)
          }}</span>
        </div>
      </div>

      <div class="plugin-sheet-grid">
        <div>
          <h4>快速治理</h4>
          <p class="soft-note">
            插件列表聚焦批量动作，这里保留单插件快速处理入口。
          </p>
          <div class="table-actions admin-action-cluster">
            <button
              v-if="selectedPlugin.status !== 'published'"
              class="btn btn-sm"
              :disabled="actionPending"
              @click="pluginAction('publish', selectedPlugin.plugin_id)"
            >
              重新上架
            </button>
            <button
              v-if="selectedPlugin.status !== 'draft'"
              class="btn btn-sm"
              :disabled="actionPending"
              @click="pluginAction('reject', selectedPlugin.plugin_id)"
            >
              退回
            </button>
            <button
              v-if="selectedPlugin.status !== 'deprecated'"
              class="btn btn-sm"
              :disabled="actionPending"
              @click="pluginAction('deprecate', selectedPlugin.plugin_id)"
            >
              下架
            </button>
            <button
              v-if="selectedPlugin.status !== 'blocked'"
              class="btn btn-sm btn-danger"
              :disabled="actionPending"
              @click="pluginAction('block', selectedPlugin.plugin_id)"
            >
              封禁
            </button>
            <button
              class="btn btn-sm btn-danger"
              :disabled="actionPending"
              @click="pluginAction('delete', selectedPlugin.plugin_id)"
            >
              删除
            </button>
          </div>
          <h4 style="margin-top: 18px">社区标识</h4>
          <div class="table-actions trust-switch-row">
            <button
              v-for="level in ['official', 'verified', 'community']"
              :key="level"
              :class="[
                'btn',
                'btn-sm',
                { 'is-active': selectedPlugin.trust_level === level },
              ]"
              :disabled="actionPending"
              @click="setTrustLevel(selectedPlugin.plugin_id, level)"
            >
              {{ trustLevelLabel(level) }}
            </button>
          </div>
        </div>
        <div>
          <h4>当前摘要</h4>
          <ul class="meta-list">
            <li>
              <span>Owner</span
              ><strong>{{
                selectedPlugin.owner_display_name ||
                selectedPlugin.owner_login ||
                selectedPlugin.owner_id
              }}</strong>
            </li>
            <li>
              <span>最新版本</span
              ><strong>{{ selectedPlugin.latest_version || '-' }}</strong>
            </li>
            <li>
              <span>分类</span
              ><strong>{{
                (selectedPlugin.categories || [])
                  .map(categoryLabel)
                  .join(' / ') || '未设置'
              }}</strong>
            </li>
            <li>
              <span>标签</span
              ><strong>{{
                (selectedPlugin.tags || []).join(' / ') || '未设置'
              }}</strong>
            </li>
            <li>
              <span>热度</span
              ><strong
                >{{ formatNumber(selectedPlugin.likes_count) }} 订阅 ·
                {{ formatNumber(selectedPlugin.downloads_count) }} 下载</strong
              >
            </li>
            <li>
              <span>最近治理</span
              ><strong>{{ formatRelative(selectedPlugin.updated_at) }}</strong>
            </li>
          </ul>
        </div>
      </div>

      <div
        v-if="snapshot?.recent_reviews?.length"
        class="review-feed"
        style="margin-top: 16px"
      >
        <article
          v-for="item in snapshot.recent_reviews.slice(0, 6)"
          :key="item.id || item.created_at"
          class="review-feed-item"
        >
          <div>
            <strong>{{ item.action }}</strong>
            <p>
              {{ item.target_id }} · {{ item.status_before || '-' }} →
              {{ item.status_after || '-' }}
            </p>
          </div>
          <div class="review-feed-meta">
            <span>{{ item.operator_id }}</span>
            <span>{{ formatRelative(item.created_at) }}</span>
          </div>
        </article>
      </div>
    </section>

    <section v-else class="panel">
      <EmptyState
        title="未选择插件"
        message="从表格中选择一个插件后，这里会展示快速治理面板。"
      />
    </section>

    <BulkActionBar
      :selected-count="admin.selectedIds.length"
      :pending="admin.bulkPending"
      :actions="bulkActions"
      @confirm="applyBulkAction"
    />
  </div>
</template>
<style scoped>
.admin-plugins-view {
  display: grid;
  gap: 20px;
}
.plugin-sheet-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 32px;
  padding-top: 14px;
}
.plugin-sheet-grid h4 {
  margin: 0 0 12px;
  font-size: 13px;
}
.plugin-sheet-grid > div + div {
  border-left: 1px solid var(--line);
  padding-left: 32px;
}
.admin-action-cluster {
  padding-top: 10px;
}
.trust-switch-row .is-active {
  color: var(--blue-500);
  border-color: var(--blue-500);
  background: var(--blue-50);
}
@media (max-width: 760px) {
  .plugin-sheet-grid {
    grid-template-columns: 1fr;
    gap: 24px;
  }
  .plugin-sheet-grid > div + div {
    border: 0;
    border-top: 1px solid var(--line);
    padding: 20px 0 0;
  }
}
</style>
