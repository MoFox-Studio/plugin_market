<script setup lang="ts">
import { useMarketDialog } from '@/composables/useMarketDialog';
const { confirm: confirmAction, prompt: promptAction } = useMarketDialog();
import MarketSelect from '@/components/MarketSelect.vue';
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import api from '@/api';
import { useToastStore } from '@/stores/toast';
import { formatRelative } from '@/utils/format';
import type { Comment, Plugin } from '@/types';
import PageSkeleton from '@/components/PageSkeleton.vue';
import EmptyState from '@/components/EmptyState.vue';

interface CommentListResponse {
  items: Comment[];
  total: number;
}

const toast = useToastStore();

const loadingPlugins = ref(true);
const loadingComments = ref(false);
const plugins = ref<Plugin[]>([]);
const selectedPluginId = ref('');
const comments = ref<Comment[]>([]);
const total = ref(0);
const query = ref('');
const showDeleted = ref(true);
const pluginsError = ref('');
const commentsError = ref('');
const deletingId = ref<string | null>(null);
let commentsRequest = 0;
let pluginsRequest = 0;
let disposed = false;

const filteredComments = computed(() =>
  comments.value.filter((item) => {
    const matchesQuery =
      !query.value.trim() ||
      item.content.toLowerCase().includes(query.value.trim().toLowerCase()) ||
      String(item.author.display_name || '')
        .toLowerCase()
        .includes(query.value.trim().toLowerCase());
    const matchesDeleted = showDeleted.value || !item.is_deleted;
    return matchesQuery && matchesDeleted;
  }),
);

async function loadPlugins(): Promise<void> {
  const request = ++pluginsRequest;
  loadingPlugins.value = true;
  pluginsError.value = '';
  try {
    const result = await api.get('/api/v1/admin/plugins');
    if (disposed || request !== pluginsRequest) return;
    plugins.value = result.items || [];
    if (!selectedPluginId.value && plugins.value.length)
      selectedPluginId.value = plugins.value[0].plugin_id;
  } catch (e) {
    if (!disposed && request === pluginsRequest)
      pluginsError.value = (e as Error).message || '无法读取插件列表';
  } finally {
    if (!disposed && request === pluginsRequest) loadingPlugins.value = false;
  }
}

async function loadComments(): Promise<void> {
  const request = ++commentsRequest;
  const pluginId = selectedPluginId.value;
  comments.value = [];
  total.value = 0;
  commentsError.value = '';
  if (!pluginId || disposed) {
    loadingComments.value = false;
    return;
  }
  loadingComments.value = true;
  try {
    const result = await api.get<CommentListResponse>(
      `/api/v1/plugins/${encodeURIComponent(pluginId)}/comments?limit=100`,
    );
    if (disposed || request !== commentsRequest) return;
    comments.value = result.items || [];
    total.value = result.total || 0;
  } catch (e) {
    if (!disposed && request === commentsRequest)
      commentsError.value = (e as Error).message || '无法读取评论';
  } finally {
    if (!disposed && request === commentsRequest) loadingComments.value = false;
  }
}

async function deleteComment(commentId: string): Promise<void> {
  const pluginId = selectedPluginId.value;
  if (
    !pluginId ||
    deletingId.value ||
    !(await confirmAction(`确认删除评论 #${commentId} 吗？`))
  )
    return;
  deletingId.value = commentId;
  try {
    await api.del(
      `/api/v1/plugins/${encodeURIComponent(pluginId)}/comments/${encodeURIComponent(commentId)}`,
    );
    if (disposed) return;
    toast.show('评论已删除', 'ok');
    if (pluginId === selectedPluginId.value) await loadComments();
  } catch (e) {
    if (!disposed) toast.show((e as Error).message || '删除失败', 'error');
  } finally {
    deletingId.value = null;
  }
}

watch(selectedPluginId, () => {
  void loadComments();
});
onMounted(() => {
  void loadPlugins();
});
onBeforeUnmount(() => {
  disposed = true;
  pluginsRequest++;
  commentsRequest++;
});
</script>

<template>
  <section class="admin-subview-stack">
    <section class="panel">
      <div class="section-head compact-head">
        <div>
          <h1 class="desk-title">评论审核</h1>
          <p>
            按插件查看最近的讨论，处理需要移除的评论。删除后的记录保留状态标记。
          </p>
        </div>
      </div>

      <div v-if="pluginsError" class="admin-error" role="alert">
        <p>{{ pluginsError }}</p>
        <button class="btn" @click="loadPlugins">重新加载插件</button>
      </div>
      <fieldset class="queue-table-filters admin-plugins-filters">
        <legend>查找评论</legend>
        <label class="desk-field">
          <span>插件</span>
          <MarketSelect
            class="profile-editor-input"
            aria-label="选择插件"
            :value="selectedPluginId"
            :disabled="loadingPlugins"
            @change="
              selectedPluginId = ($event.target as HTMLSelectElement).value
            "
          >
            <option value="">选择插件</option>
            <option
              v-for="plugin in plugins"
              :key="plugin.plugin_id"
              :value="plugin.plugin_id"
            >
              {{ plugin.display_name }} · {{ plugin.plugin_id }}
            </option>
          </MarketSelect>
        </label>
        <label class="desk-field">
          <span>内容 / 作者</span>
          <input
            class="profile-editor-input"
            aria-label="搜索评论"
            :value="query"
            type="search"
            placeholder="搜索评论内容或作者"
            @input="query = ($event.target as HTMLInputElement).value"
          />
        </label>
        <label class="admin-filter-toggle">
          <input
            :checked="showDeleted"
            type="checkbox"
            @change="showDeleted = ($event.target as HTMLInputElement).checked"
          />
          <span>显示已删除评论</span>
        </label>
      </fieldset>
    </section>

    <PageSkeleton v-if="loadingPlugins" type="rows" :count="4" />
    <EmptyState
      v-else-if="!pluginsError && !plugins.length"
      title="暂无插件"
      message="插件发布后可在这里查看评论。"
    />
    <section class="panel" v-if="selectedPluginId">
      <div class="section-head compact-head">
        <div>
          <h2>评论列表</h2>
          <p>当前插件共 {{ total }} 条评论，展示最近 100 条。</p>
        </div>
      </div>
      <PageSkeleton v-if="loadingComments" type="rows" :count="4" />
      <div v-else-if="commentsError" class="admin-error" role="alert">
        <p>{{ commentsError }}</p>
        <button class="btn" @click="loadComments">重新加载评论</button>
      </div>
      <div v-else-if="filteredComments.length" class="review-feed">
        <article
          v-for="item in filteredComments"
          :key="item.id"
          class="review-feed-item"
        >
          <div>
            <strong
              >{{ item.author.display_name }} · @{{
                item.author.github_login
              }}</strong
            >
            <p>{{ item.content }}</p>
            <small class="soft-note"
              >{{ formatRelative(item.created_at) }} ·
              {{ item.is_deleted ? '已删除' : '可见' }}</small
            >
          </div>
          <div class="table-actions">
            <button
              v-if="!item.is_deleted"
              class="btn btn-sm btn-danger"
              type="button"
              :disabled="!!deletingId"
              @click="deleteComment(item.id)"
            >
              删除
            </button>
          </div>
        </article>
      </div>
      <EmptyState
        v-else
        title="暂无评论"
        message="换一个插件或放宽筛选条件试试。"
      />
    </section>
  </section>
</template>
